from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .analytics import ZoneEngine
from .annotator import annotate_frame, encode_jpeg
from .contracts import (
    AppConfig,
    CameraState,
    Event,
    SourceSelection,
    SourceStatus,
    TrackObservation,
    ZoneConfig,
    ZoneMetric,
)
from .demo_video import ensure_demo_video
from .detectors import PersonDetector, create_detector
from .events import EventEngine
from .repository import AnalyticsRepository
from .time import utc_now
from .tracking import ByteTrackAdapter, MultiObjectTracker
from .video_sources import VideoSource, create_source

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class LiveState:
    camera: CameraState
    metrics: list[ZoneMetric]
    tracks: list[TrackObservation]
    latest_events: list[Event]
    zones: list[ZoneConfig]
    zone_revision: int


class VideoPipeline:
    def __init__(
        self, config: AppConfig, repository: AnalyticsRepository, zone_revision: int = 1
    ) -> None:
        self.config = config
        self.repository = repository
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._source: VideoSource | None = None
        self._detector: PersonDetector | None = None
        self._tracker: MultiObjectTracker | None = None
        self._zone_engine = ZoneEngine(
            config.camera.camera_id,
            [zone for zone in config.zones if zone.enabled],
            config.analytics,
        )
        self._event_engine = EventEngine(config.camera.camera_id)
        self._metrics: list[ZoneMetric] = []
        self._tracks: list[TrackObservation] = []
        self._latest_events: list[Event] = []
        self._jpeg: bytes | None = None
        self._show_overlays = True
        self._offline_event_sent = False
        self._zone_revision = zone_revision
        self.camera = CameraState(
            camera_id=config.camera.camera_id,
            name=config.camera.name,
            source_type=config.camera.source_type,
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.camera.status = SourceStatus.STARTING
        self._thread = threading.Thread(target=self._run, name="veratex-pipeline", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        if self._source:
            self._source.close()
        self.camera.status = SourceStatus.STOPPED

    def select_source(self, selection: SourceSelection) -> None:
        self.stop()
        self.config.camera.source_type = selection.source_type
        self.config.camera.source = selection.source
        self.config.camera.detector = selection.detector
        self.camera.source_type = selection.source_type
        self.start()

    def reset(self) -> None:
        with self._lock:
            self._zone_engine.reset()
            if self._tracker:
                self._tracker.reset()
            self._metrics = []
            self._tracks = []
            self._latest_events = []

    def toggle_overlays(self, enabled: bool) -> None:
        self._show_overlays = enabled

    def replace_zones(self, zones: list[ZoneConfig], revision: int) -> None:
        active_zones = [zone for zone in zones if zone.enabled]
        with self._lock:
            self.config.zones = zones
            self._zone_engine.reconfigure(active_zones)
            self._metrics = [
                metric
                for metric in self._metrics
                if any(zone.zone_id == metric.zone_id for zone in active_zones)
            ]
            self._zone_revision = revision

    def snapshot(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    def live_state(self) -> LiveState:
        with self._lock:
            return LiveState(
                camera=self.camera.model_copy(deep=True),
                metrics=[item.model_copy(deep=True) for item in self._metrics],
                tracks=[item.model_copy(deep=True) for item in self._tracks],
                latest_events=[item.model_copy(deep=True) for item in self._latest_events],
                zones=[item.model_copy(deep=True) for item in self.config.zones],
                zone_revision=self._zone_revision,
            )

    def _prepare(self) -> None:
        camera = self.config.camera
        if camera.source_type == "file_loop" and camera.detector == "synthetic":
            ensure_demo_video(Path(str(camera.source)))
        self._source = create_source(camera.source_type, camera.source, camera.loop)
        self._source.open()
        self._detector = create_detector(camera.detector, camera.confidence)
        self._tracker = ByteTrackAdapter(frame_rate=round(camera.inference_fps))
        self.camera.fps_input = self._source.fps

    def _run(self) -> None:
        camera = self.config.camera
        last_inference = 0.0
        last_metric = 0.0
        frame_count = 0
        fps_window = time.monotonic()
        failure_since: float | None = None
        try:
            while not self._stop.is_set():
                try:
                    if self._source is None:
                        self._prepare()
                    packet = self._source.read()
                    if packet is None:
                        raise RuntimeError("Source returned no frame")
                    started = time.perf_counter()
                    now_mono = time.monotonic()
                    self.camera.status = SourceStatus.ONLINE
                    self.camera.last_error = None
                    self.camera.last_frame_at = packet.captured_at
                    self._offline_event_sent = False
                    failure_since = None
                    frame_count += 1
                    if now_mono - fps_window >= 1:
                        self.camera.fps_input = frame_count / (now_mono - fps_window)
                        frame_count = 0
                        fps_window = now_mono
                    if now_mono - last_inference >= 1 / camera.inference_fps:
                        detections = self._detector.detect(packet.frame)
                        anonymous_tracks = self._tracker.update(detections)
                        height, width = packet.frame.shape[:2]
                        tracks, metrics, transitions = self._zone_engine.update(
                            anonymous_tracks, (width, height), now_mono, packet.captured_at
                        )
                        events = self._event_engine.from_transitions(transitions)
                        if events:
                            self.repository.add_events(events)
                        if now_mono - last_metric >= self.config.analytics.metric_interval_seconds:
                            self.repository.add_metrics(metrics)
                            last_metric = now_mono
                        with self._lock:
                            self._tracks = tracks
                            self._metrics = metrics
                            self._latest_events = (events + self._latest_events)[:20]
                        last_inference = now_mono
                        self.camera.fps_inference = camera.inference_fps
                    with self._lock:
                        annotated = annotate_frame(
                            packet.frame,
                            [zone for zone in self.config.zones if zone.enabled],
                            self._tracks,
                            self._show_overlays,
                        )
                        self._jpeg = encode_jpeg(annotated)
                    self.camera.processing_latency_ms = round(
                        (time.perf_counter() - started) * 1000, 1
                    )
                    target_delay = max(
                        0.0, 1 / camera.display_fps - (time.perf_counter() - started)
                    )
                    self._stop.wait(target_delay)
                except Exception as exc:
                    LOGGER.warning("video_source_failure", extra={"error": str(exc)})
                    self.camera.dropped_frames += 1
                    self.camera.last_error = str(exc)
                    failure_since = failure_since or time.monotonic()
                    offline_duration = time.monotonic() - failure_since
                    is_offline = offline_duration >= camera.offline_after_seconds
                    self.camera.status = (
                        SourceStatus.OFFLINE if is_offline else SourceStatus.DEGRADED
                    )
                    if self._source:
                        self._source.close()
                        self._source = None
                    if is_offline and not self._offline_event_sent:
                        event = Event(
                            event_id=__import__("uuid").uuid4().hex,
                            camera_id=camera.camera_id,
                            zone_id=None,
                            event_type="source_offline",
                            severity="critical",
                            occurred_at=utc_now(),
                            attributes={"message": str(exc)},
                        )
                        self.repository.add_events([event])
                        with self._lock:
                            self._latest_events = [event, *self._latest_events][:20]
                        self._offline_event_sent = True
                    self._stop.wait(camera.reconnect_seconds)
        finally:
            if self._source:
                self._source.close()
                self._source = None
            if self.camera.status != SourceStatus.STOPPED:
                self.camera.status = SourceStatus.STOPPED

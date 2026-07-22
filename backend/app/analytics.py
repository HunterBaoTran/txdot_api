from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

import cv2
import numpy as np

from .contracts import AnalyticsConfig, TrackObservation, ZoneConfig, ZoneMetric
from .tracking import AnonymousTrack


@dataclass(slots=True)
class ZoneTransition:
    zone_id: str
    zone_name: str
    zone_type: str
    transition_type: str
    occurred_at: datetime
    track_id: int | None
    occupancy: int
    capacity: int
    dwell_seconds: float | None = None


@dataclass(slots=True)
class _VisitState:
    active: bool = False
    inside_streak: int = 0
    outside_streak: int = 0
    entered_monotonic: float | None = None
    dwell_alerted: bool = False


@dataclass(slots=True)
class _ZoneTotals:
    entries: int = 0
    exits: int = 0
    completed_dwells: list[float] = field(default_factory=list)


def point_in_normalized_polygon(
    point_pixels: tuple[float, float],
    polygon: list[tuple[float, float]],
    frame_size: tuple[int, int],
) -> bool:
    width, height = frame_size
    pixel_polygon = np.asarray([(x * width, y * height) for x, y in polygon], dtype=np.float32)
    return cv2.pointPolygonTest(pixel_polygon, point_pixels, False) >= 0


class ZoneEngine:
    def __init__(self, camera_id: str, zones: list[ZoneConfig], config: AnalyticsConfig) -> None:
        self.camera_id = camera_id
        self.zones = zones
        self.config = config
        self._visits: dict[tuple[str, int], _VisitState] = {}
        self._totals: dict[str, _ZoneTotals] = defaultdict(_ZoneTotals)
        self._last_occupancy: dict[str, int] = defaultdict(int)

    def update(
        self,
        tracks: list[AnonymousTrack],
        frame_size: tuple[int, int],
        now_monotonic: float,
        now_utc: datetime,
    ) -> tuple[list[TrackObservation], list[ZoneMetric], list[ZoneTransition]]:
        observations: list[TrackObservation] = []
        transitions: list[ZoneTransition] = []
        present_ids = {track.track_id for track in tracks}
        memberships: dict[int, list[str]] = defaultdict(list)

        for zone in self.zones:
            for track in tracks:
                x1, _, x2, y2 = track.bbox_xyxy
                inside = point_in_normalized_polygon(
                    ((x1 + x2) / 2, y2), zone.polygon_normalized, frame_size
                )
                state = self._visits.setdefault((zone.zone_id, track.track_id), _VisitState())
                self._advance_visit(
                    zone, track.track_id, inside, state, now_monotonic, now_utc, transitions
                )
                if state.active:
                    memberships[track.track_id].append(zone.zone_id)

            for (zone_id, track_id), state in list(self._visits.items()):
                if zone_id == zone.zone_id and track_id not in present_ids and state.active:
                    self._advance_visit(
                        zone, track_id, False, state, now_monotonic, now_utc, transitions
                    )

            occupancy = self._occupancy(zone.zone_id)
            previous = self._last_occupancy[zone.zone_id]
            if previous == 0 < occupancy:
                transitions.append(
                    self._transition(zone, "zone_occupied", now_utc, None, occupancy)
                )
            if previous > 0 == occupancy:
                transitions.append(self._transition(zone, "zone_vacant", now_utc, None, occupancy))
            if previous < zone.capacity <= occupancy:
                transitions.append(
                    self._transition(zone, "capacity_reached", now_utc, None, occupancy)
                )
            self._last_occupancy[zone.zone_id] = occupancy

        for track in tracks:
            observations.append(
                TrackObservation(
                    camera_id=self.camera_id,
                    track_id=track.track_id,
                    timestamp=now_utc,
                    confidence=track.confidence,
                    bbox_xyxy=track.bbox_xyxy,
                    zone_ids=memberships[track.track_id],
                )
            )
        metrics = [self._metric(zone, now_monotonic, now_utc) for zone in self.zones]
        return observations, metrics, transitions

    def _advance_visit(
        self,
        zone: ZoneConfig,
        track_id: int,
        inside: bool,
        state: _VisitState,
        now_monotonic: float,
        now_utc: datetime,
        transitions: list[ZoneTransition],
    ) -> None:
        state.inside_streak = state.inside_streak + 1 if inside else 0
        state.outside_streak = state.outside_streak + 1 if not inside else 0
        if not state.active and state.inside_streak >= self.config.enter_debounce_frames:
            state.active = True
            state.entered_monotonic = now_monotonic
            state.dwell_alerted = False
            self._totals[zone.zone_id].entries += 1
            transitions.append(
                self._transition(
                    zone, "zone_entered", now_utc, track_id, self._occupancy(zone.zone_id)
                )
            )
        if state.active and state.entered_monotonic is not None:
            dwell = max(0.0, now_monotonic - state.entered_monotonic)
            if dwell >= zone.dwell_alert_seconds and not state.dwell_alerted:
                state.dwell_alerted = True
                transition = self._transition(
                    zone,
                    "dwell_threshold_exceeded",
                    now_utc,
                    track_id,
                    self._occupancy(zone.zone_id),
                )
                transition.dwell_seconds = dwell
                transitions.append(transition)
        if state.active and state.outside_streak >= self.config.exit_debounce_frames:
            dwell = max(0.0, now_monotonic - (state.entered_monotonic or now_monotonic))
            self._totals[zone.zone_id].exits += 1
            self._totals[zone.zone_id].completed_dwells.append(dwell)
            state.active = False
            state.entered_monotonic = None
            transition = self._transition(
                zone, "zone_exited", now_utc, track_id, self._occupancy(zone.zone_id)
            )
            transition.dwell_seconds = dwell
            transitions.append(transition)

    def _occupancy(self, zone_id: str) -> int:
        return sum(
            1
            for (item_zone, _), state in self._visits.items()
            if item_zone == zone_id and state.active
        )

    def _metric(self, zone: ZoneConfig, now_monotonic: float, now_utc: datetime) -> ZoneMetric:
        occupancy = self._occupancy(zone.zone_id)
        totals = self._totals[zone.zone_id]
        dwells = list(totals.completed_dwells)
        dwells.extend(
            now_monotonic - state.entered_monotonic
            for (zone_id, _), state in self._visits.items()
            if zone_id == zone.zone_id and state.active and state.entered_monotonic is not None
        )
        return ZoneMetric(
            camera_id=self.camera_id,
            zone_id=zone.zone_id,
            timestamp=now_utc,
            occupancy=occupancy,
            capacity=zone.capacity,
            utilization_pct=round(occupancy / zone.capacity * 100, 1),
            entries_total=totals.entries,
            exits_total=totals.exits,
            average_dwell_seconds=round(sum(dwells) / len(dwells), 1) if dwells else 0,
        )

    @staticmethod
    def _transition(
        zone: ZoneConfig, kind: str, occurred_at: datetime, track_id: int | None, occupancy: int
    ) -> ZoneTransition:
        return ZoneTransition(
            zone_id=zone.zone_id,
            zone_name=zone.name,
            zone_type=zone.zone_type,
            transition_type=kind,
            occurred_at=occurred_at,
            track_id=track_id,
            occupancy=occupancy,
            capacity=zone.capacity,
        )

    def reset(self) -> None:
        self._visits.clear()
        self._totals.clear()
        self._last_occupancy.clear()

    def reconfigure(self, zones: list[ZoneConfig]) -> None:
        previous = {zone.zone_id: zone for zone in self.zones}
        current = {zone.zone_id: zone for zone in zones}
        changed = {
            zone_id
            for zone_id in previous.keys() | current.keys()
            if previous.get(zone_id) != current.get(zone_id)
        }
        self._visits = {key: state for key, state in self._visits.items() if key[0] not in changed}
        for zone_id in changed:
            self._last_occupancy.pop(zone_id, None)
        self.zones = zones

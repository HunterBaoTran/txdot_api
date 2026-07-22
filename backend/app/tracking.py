from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import supervision as sv

from .contracts import Detection


@dataclass(slots=True)
class AnonymousTrack:
    track_id: int
    bbox_xyxy: tuple[float, float, float, float]
    confidence: float


class MultiObjectTracker(ABC):
    @abstractmethod
    def update(self, detections: list[Detection]) -> list[AnonymousTrack]: ...

    @abstractmethod
    def reset(self) -> None: ...


class ByteTrackAdapter(MultiObjectTracker):
    """Thin adapter around the maintained Supervision ByteTrack implementation."""

    def __init__(self, frame_rate: int = 5) -> None:
        self.frame_rate = max(frame_rate, 1)
        self._tracker = sv.ByteTrack(frame_rate=self.frame_rate, minimum_consecutive_frames=1)

    def update(self, detections: list[Detection]) -> list[AnonymousTrack]:
        if detections:
            sv_detections = sv.Detections(
                xyxy=np.asarray([item.bbox_xyxy for item in detections], dtype=np.float32),
                confidence=np.asarray([item.confidence for item in detections], dtype=np.float32),
                class_id=np.zeros(len(detections), dtype=int),
            )
        else:
            sv_detections = sv.Detections.empty()
        tracked = self._tracker.update_with_detections(sv_detections)
        if tracked.tracker_id is None:
            return []
        return [
            AnonymousTrack(
                track_id=int(track_id),
                bbox_xyxy=tuple(float(value) for value in box),
                confidence=float(confidence),
            )
            for box, confidence, track_id in zip(
                tracked.xyxy, tracked.confidence, tracked.tracker_id, strict=True
            )
        ]

    def reset(self) -> None:
        self._tracker = sv.ByteTrack(frame_rate=self.frame_rate, minimum_consecutive_frames=1)

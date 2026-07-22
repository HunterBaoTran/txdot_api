from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class SourceStatus(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class UTCModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("*", when_used="json", check_fields=False)
    def serialize_datetime(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat().replace("+00:00", "Z")
        return value


class Detection(BaseModel):
    bbox_xyxy: tuple[float, float, float, float]
    confidence: float
    class_name: str = "person"


class TrackObservation(UTCModel):
    camera_id: str
    track_id: int
    timestamp: datetime
    class_name: str = "person"
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]
    zone_ids: list[str] = Field(default_factory=list)


class ZoneConfig(BaseModel):
    zone_id: str
    name: str
    zone_type: str
    polygon_normalized: list[tuple[float, float]]
    capacity: int = Field(ge=1)
    dwell_alert_seconds: float = Field(default=900, ge=0)


class CameraConfig(BaseModel):
    camera_id: str
    name: str
    source_type: str
    source: str | int
    detector: str = "yolo"
    inference_fps: float = Field(default=5, gt=0)
    display_fps: float = Field(default=15, gt=0)
    confidence: float = Field(default=0.35, ge=0, le=1)
    loop: bool = True
    auto_start: bool = True
    reconnect_seconds: float = Field(default=1, gt=0)
    offline_after_seconds: float = Field(default=3, gt=0)


class AnalyticsConfig(BaseModel):
    enter_debounce_frames: int = Field(default=2, ge=1)
    exit_debounce_frames: int = Field(default=2, ge=1)
    metric_interval_seconds: float = Field(default=1, gt=0)


class AppConfig(BaseModel):
    camera: CameraConfig
    zones: list[ZoneConfig]
    analytics: AnalyticsConfig = AnalyticsConfig()


class CameraState(UTCModel):
    camera_id: str
    name: str
    source_type: str
    status: SourceStatus = SourceStatus.STOPPED
    fps_input: float = 0
    fps_inference: float = 0
    last_frame_at: datetime | None = None
    processing_latency_ms: float = 0
    dropped_frames: int = 0
    last_error: str | None = None


class Event(UTCModel):
    event_id: str
    camera_id: str
    zone_id: str | None
    event_type: str
    severity: str
    occurred_at: datetime
    track_id: int | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    snapshot_ref: str | None = None
    feedback_status: str | None = None
    feedback_reason: str | None = None


class ZoneMetric(UTCModel):
    camera_id: str
    zone_id: str
    timestamp: datetime
    occupancy: int
    capacity: int
    utilization_pct: float
    entries_total: int
    exits_total: int
    average_dwell_seconds: float


class SummaryPoint(UTCModel):
    timestamp: datetime
    occupancy: float
    utilization_pct: float


class FeedbackRequest(BaseModel):
    status: str = Field(pattern="^(acknowledged|dismissed)$")
    reason: str | None = Field(default=None, max_length=500)


class SourceSelection(BaseModel):
    source_type: str = Field(pattern="^(file_loop|webcam)$")
    source: str | int
    detector: str = Field(default="yolo", pattern="^(yolo|synthetic)$")

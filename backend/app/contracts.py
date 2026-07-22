from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from .zones import polygon_area, polygon_self_intersects


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
    zone_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    name: str = Field(min_length=1, max_length=80)
    zone_type: str = Field(pattern="^(table|seat|queue|dealer|restricted)$")
    polygon_normalized: list[tuple[float, float]] = Field(min_length=3, max_length=32)
    capacity: int = Field(ge=1)
    dwell_alert_seconds: float = Field(default=900, ge=0)
    enabled: bool = True
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")

    @model_validator(mode="after")
    def validate_polygon(self) -> ZoneConfig:
        if any(x < 0 or x > 1 or y < 0 or y > 1 for x, y in self.polygon_normalized):
            raise ValueError("polygon coordinates must be between 0 and 1")
        unique = {(round(x, 6), round(y, 6)) for x, y in self.polygon_normalized}
        if len(unique) != len(self.polygon_normalized):
            raise ValueError("polygon points must be unique")
        if polygon_self_intersects(self.polygon_normalized):
            raise ValueError("polygon cannot intersect itself")
        if polygon_area(self.polygon_normalized) < 0.0005:
            raise ValueError("polygon area is too small")
        return self


class ZoneCollection(UTCModel):
    camera_id: str
    revision: int
    updated_at: datetime
    zones: list[ZoneConfig]


class ZoneMutationRequest(BaseModel):
    revision: int = Field(ge=0)
    zone: ZoneConfig


class ZonePresetRequest(BaseModel):
    revision: int = Field(ge=0)


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

from __future__ import annotations

from uuid import uuid4

from .analytics import ZoneTransition
from .contracts import Event


class EventEngine:
    SEVERITIES = {
        "capacity_reached": "warning",
        "dwell_threshold_exceeded": "warning",
        "source_offline": "critical",
    }

    def __init__(self, camera_id: str) -> None:
        self.camera_id = camera_id

    def from_transitions(self, transitions: list[ZoneTransition]) -> list[Event]:
        return [
            Event(
                event_id=str(uuid4()),
                camera_id=self.camera_id,
                zone_id=item.zone_id,
                event_type=item.transition_type,
                severity=self.SEVERITIES.get(item.transition_type, "info"),
                occurred_at=item.occurred_at,
                track_id=item.track_id,
                attributes={
                    "zone_name": item.zone_name,
                    "zone_type": item.zone_type,
                    "occupancy": item.occupancy,
                    "capacity": item.capacity,
                    **(
                        {"dwell_seconds": round(item.dwell_seconds, 1)}
                        if item.dwell_seconds is not None
                        else {}
                    ),
                },
            )
            for item in transitions
        ]

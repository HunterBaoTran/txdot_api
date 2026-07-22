from datetime import UTC, datetime

from app.analytics import ZoneTransition
from app.events import EventEngine


def test_event_contract_and_severity() -> None:
    event = EventEngine("camera-1").from_transitions(
        [
            ZoneTransition(
                zone_id="seat-1",
                transition_type="capacity_reached",
                occurred_at=datetime(2026, 7, 21, tzinfo=UTC),
                track_id=3,
                occupancy=1,
                capacity=1,
            )
        ]
    )[0]
    assert event.severity == "warning"
    assert event.attributes == {"occupancy": 1, "capacity": 1}
    assert event.model_dump(mode="json")["occurred_at"].endswith("Z")

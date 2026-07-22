from datetime import UTC, datetime

from app.analytics import ZoneEngine, point_in_normalized_polygon
from app.contracts import AnalyticsConfig, ZoneConfig
from app.tracking import AnonymousTrack

ZONE = ZoneConfig(
    zone_id="seat-1",
    name="Seat 1",
    zone_type="seat",
    polygon_normalized=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
    capacity=1,
    dwell_alert_seconds=5,
)
NOW = datetime(2026, 7, 21, tzinfo=UTC)


def track(x: float = 50, y: float = 50) -> AnonymousTrack:
    return AnonymousTrack(track_id=7, bbox_xyxy=(x - 5, y - 20, x + 5, y), confidence=0.9)


def test_normalized_polygon_membership_scales() -> None:
    assert point_in_normalized_polygon((50, 50), ZONE.polygon_normalized, (100, 100))
    assert not point_in_normalized_polygon((5, 50), ZONE.polygon_normalized, (100, 100))


def test_entry_and_exit_are_debounced_and_dwell_is_accumulated() -> None:
    engine = ZoneEngine(
        "cam", [ZONE], AnalyticsConfig(enter_debounce_frames=2, exit_debounce_frames=2)
    )
    _, metrics, events = engine.update([track()], (100, 100), 10, NOW)
    assert metrics[0].occupancy == 0
    assert events == []

    _, metrics, events = engine.update([track()], (100, 100), 11, NOW)
    assert metrics[0].occupancy == 1
    assert {event.transition_type for event in events} == {
        "zone_entered",
        "zone_occupied",
        "capacity_reached",
    }

    _, _, events = engine.update([track()], (100, 100), 16, NOW)
    assert [event.transition_type for event in events] == ["dwell_threshold_exceeded"]
    _, _, events = engine.update([track()], (100, 100), 17, NOW)
    assert events == []

    engine.update([], (100, 100), 18, NOW)
    _, metrics, events = engine.update([], (100, 100), 19, NOW)
    assert metrics[0].occupancy == 0
    assert metrics[0].entries_total == 1
    assert metrics[0].exits_total == 1
    assert metrics[0].average_dwell_seconds == 8
    assert {event.transition_type for event in events} == {"zone_exited", "zone_vacant"}

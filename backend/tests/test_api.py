from datetime import UTC, datetime

from app.contracts import Event
from fastapi.testclient import TestClient


def test_health_and_api_schemas(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["database"] == "online"

    cameras = client.get("/api/v1/cameras")
    assert cameras.status_code == 200
    assert cameras.json()[0]["camera_id"] == "test-camera"

    zones = client.get("/api/v1/zones")
    assert zones.status_code == 200
    assert zones.json()[0]["capacity"] == 1

    assert client.get("/api/v1/cameras/not-real").status_code == 404
    assert client.get("/api/v1/cameras/test-camera/snapshot").status_code == 503


def test_source_control_and_feedback_validation(client: TestClient) -> None:
    stopped = client.post("/api/v1/cameras/test-camera/stop")
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
    invalid = client.post("/api/v1/events/nope/feedback", json={"status": "unreviewed"})
    assert invalid.status_code == 422


def test_analyst_feedback_is_persisted(client: TestClient) -> None:
    event = Event(
        event_id="11111111-1111-1111-1111-111111111111",
        camera_id="test-camera",
        zone_id="seat-1",
        event_type="zone_entered",
        severity="info",
        occurred_at=datetime(2026, 7, 21, tzinfo=UTC),
        track_id=4,
    )
    client.app.state.repository.add_events([event])
    response = client.post(
        f"/api/v1/events/{event.event_id}/feedback",
        json={"status": "acknowledged", "reason": "Reviewed"},
    )
    assert response.status_code == 200
    assert response.json()["feedback_status"] == "acknowledged"
    assert response.json()["feedback_reason"] == "Reviewed"

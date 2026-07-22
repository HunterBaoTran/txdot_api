import time
from datetime import UTC, datetime

import pytest
from app.contracts import Event, ZoneConfig
from app.main import create_app
from app.repository import SqlAlchemyRepository, ZoneRevisionConflict
from fastapi.testclient import TestClient
from pydantic import ValidationError


def zone_payload(zone_id: str = "queue-1") -> dict[str, object]:
    return {
        "zone_id": zone_id,
        "name": "Guest Queue",
        "zone_type": "queue",
        "polygon_normalized": [[0.1, 0.1], [0.4, 0.1], [0.4, 0.5], [0.1, 0.5]],
        "capacity": 4,
        "dwell_alert_seconds": 30,
        "enabled": True,
        "color": "#e1a44e",
    }


def test_polygon_validation_rejects_self_intersection_and_out_of_range() -> None:
    with pytest.raises(ValidationError, match="intersect itself"):
        ZoneConfig(
            **{
                **zone_payload(),
                "polygon_normalized": [[0.1, 0.1], [0.8, 0.8], [0.8, 0.1], [0.1, 0.8]],
            }
        )
    with pytest.raises(ValidationError, match="between 0 and 1"):
        ZoneConfig(
            **{
                **zone_payload(),
                "polygon_normalized": [[-0.1, 0.1], [0.4, 0.1], [0.4, 0.5]],
            }
        )


def test_zone_crud_revisions_and_live_reload(client: TestClient) -> None:
    initial = client.get("/api/v1/cameras/test-camera/zones").json()
    assert initial["revision"] == 1

    created = client.post(
        "/api/v1/cameras/test-camera/zones",
        json={"revision": 1, "zone": zone_payload()},
    )
    assert created.status_code == 201
    assert created.json()["revision"] == 2
    assert any(zone["zone_id"] == "queue-1" for zone in created.json()["zones"])
    assert any(zone.zone_id == "queue-1" for zone in client.app.state.pipeline.live_state().zones)

    stale = client.post(
        "/api/v1/cameras/test-camera/zones",
        json={"revision": 1, "zone": zone_payload("queue-2")},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["current_revision"] == 2

    changed = zone_payload()
    changed["name"] = "VIP Queue"
    updated = client.put(
        "/api/v1/cameras/test-camera/zones/queue-1",
        json={"revision": 2, "zone": changed},
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 3
    assert (
        next(zone for zone in updated.json()["zones"] if zone["zone_id"] == "queue-1")["name"]
        == "VIP Queue"
    )

    preset = client.post(
        "/api/v1/cameras/test-camera/zones/presets/six-seat-table",
        json={"revision": 3},
    )
    assert preset.status_code == 200
    assert preset.json()["revision"] == 4
    assert [zone["zone_id"] for zone in preset.json()["zones"]] == ["seat-1"]


def test_zone_delete_preserves_historical_events(client: TestClient) -> None:
    collection = client.post(
        "/api/v1/cameras/test-camera/zones",
        json={"revision": 1, "zone": zone_payload()},
    ).json()
    client.app.state.repository.add_events(
        [
            Event(
                event_id="22222222-2222-2222-2222-222222222222",
                camera_id="test-camera",
                zone_id="queue-1",
                event_type="zone_entered",
                severity="info",
                occurred_at=datetime(2026, 7, 22, tzinfo=UTC),
                attributes={"zone_name": "Guest Queue", "zone_type": "queue"},
            )
        ]
    )
    deleted = client.delete(
        f"/api/v1/cameras/test-camera/zones/queue-1?revision={collection['revision']}"
    )
    assert deleted.status_code == 200
    assert all(zone["zone_id"] != "queue-1" for zone in deleted.json()["zones"])
    events = client.get("/api/v1/events").json()
    assert any(event["zone_id"] == "queue-1" for event in events)


def test_zone_repository_survives_restart_and_detects_conflict(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'zones.db'}"
    repository = SqlAlchemyRepository(database_url)
    seed = ZoneConfig(**zone_payload("seed-zone"))
    repository.seed_zones("camera", [seed])
    repository.create_zone("camera", ZoneConfig(**zone_payload()), 1)

    restarted = SqlAlchemyRepository(database_url)
    collection = restarted.seed_zones("camera", [seed])
    assert collection.revision == 2
    assert {zone.zone_id for zone in collection.zones} == {"seed-zone", "queue-1"}
    with pytest.raises(ZoneRevisionConflict):
        restarted.delete_zone("camera", "queue-1", expected_revision=1)


def test_saved_zone_drives_metrics_on_next_inference_cycle(tmp_path, test_config) -> None:
    test_config.camera.auto_start = True
    test_config.camera.source = str(tmp_path / "live-demo.mp4")
    test_config.camera.inference_fps = 10
    test_config.camera.display_fps = 20
    repository = SqlAlchemyRepository(f"sqlite:///{tmp_path / 'live.db'}")
    app = create_app(test_config, repository)
    full_frame = {
        **zone_payload("full-frame"),
        "name": "Entire Camera View",
        "polygon_normalized": [[0.01, 0.01], [0.99, 0.01], [0.99, 0.99], [0.01, 0.99]],
        "capacity": 10,
    }
    with TestClient(app) as running:
        response = running.post(
            "/api/v1/cameras/test-camera/zones",
            json={"revision": 1, "zone": full_frame},
        )
        assert response.status_code == 201
        deadline = time.monotonic() + 3
        metric = None
        while time.monotonic() < deadline:
            metrics = running.get("/api/v1/metrics/current").json()
            metric = next((item for item in metrics if item["zone_id"] == "full-frame"), None)
            if metric and metric["occupancy"] > 0:
                break
            time.sleep(0.05)
        assert metric is not None
        assert metric["occupancy"] > 0

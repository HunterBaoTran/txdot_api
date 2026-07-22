from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.contracts import AnalyticsConfig, AppConfig, CameraConfig, ZoneConfig
from app.main import create_app
from app.pipeline import VideoPipeline
from app.repository import SqlAlchemyRepository
from fastapi.testclient import TestClient


@pytest.fixture
def test_config() -> AppConfig:
    return AppConfig(
        camera=CameraConfig(
            camera_id="test-camera",
            name="Test Camera",
            source_type="file_loop",
            source="missing.mp4",
            detector="synthetic",
            auto_start=False,
        ),
        zones=[
            ZoneConfig(
                zone_id="seat-1",
                name="Seat 1",
                zone_type="seat",
                polygon_normalized=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
                capacity=1,
                dwell_alert_seconds=5,
            )
        ],
        analytics=AnalyticsConfig(enter_debounce_frames=2, exit_debounce_frames=2),
    )


@pytest.fixture
def client(tmp_path, test_config: AppConfig) -> Iterator[TestClient]:
    repository = SqlAlchemyRepository(f"sqlite:///{tmp_path / 'test.db'}")
    pipeline = VideoPipeline(test_config, repository)
    app = create_app(test_config, repository, pipeline)
    with TestClient(app) as test_client:
        yield test_client

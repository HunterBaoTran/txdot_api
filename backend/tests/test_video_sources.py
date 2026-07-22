import time

from app.contracts import AppConfig
from app.demo_video import ensure_demo_video
from app.pipeline import VideoPipeline
from app.repository import SqlAlchemyRepository
from app.video_sources import FileLoopSource


def test_file_source_loops_at_end(tmp_path) -> None:
    path = ensure_demo_video(tmp_path / "short.mp4", duration_seconds=1, fps=3)
    source = FileLoopSource(str(path))
    source.open()
    try:
        packets = [source.read() for _ in range(5)]
    finally:
        source.close()
    assert all(packet is not None for packet in packets)
    assert packets[-1].sequence == 5


def test_unavailable_source_reports_health_and_recovers_without_crashing(
    tmp_path, test_config: AppConfig
) -> None:
    test_config.camera.detector = "yolo"
    test_config.camera.source = str(tmp_path / "does-not-exist.mp4")
    test_config.camera.reconnect_seconds = 0.02
    test_config.camera.offline_after_seconds = 0.05
    repository = SqlAlchemyRepository(f"sqlite:///{tmp_path / 'health.db'}")
    pipeline = VideoPipeline(test_config, repository)
    pipeline.start()
    deadline = time.monotonic() + 1
    while pipeline.live_state().camera.status != "offline" and time.monotonic() < deadline:
        time.sleep(0.01)
    state = pipeline.live_state().camera
    pipeline.stop()
    assert state.status == "offline"
    assert state.dropped_frames >= 1
    assert "does not exist" in (state.last_error or "")
    assert repository.recent_events()[0].event_type == "source_offline"

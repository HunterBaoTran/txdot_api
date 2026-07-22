from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from .config import load_config
from .contracts import (
    AppConfig,
    CameraState,
    Event,
    FeedbackRequest,
    SourceSelection,
    SummaryPoint,
    ZoneConfig,
    ZoneMetric,
)
from .pipeline import VideoPipeline
from .repository import SqlAlchemyRepository

logging.basicConfig(
    level=os.getenv("VERATEX_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app(
    config: AppConfig | None = None,
    repository: SqlAlchemyRepository | None = None,
    pipeline: VideoPipeline | None = None,
) -> FastAPI:
    app_config = config or load_config()
    repo = repository or SqlAlchemyRepository()
    runtime = pipeline or VideoPipeline(app_config, repo)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if app_config.camera.auto_start:
            runtime.start()
        yield
        runtime.stop()

    app = FastAPI(
        title="Veratex Video Intelligence API",
        version="0.1.0",
        description="Local anonymous occupancy analytics proof of concept.",
        lifespan=lifespan,
    )
    app.state.config = app_config
    app.state.repository = repo
    app.state.pipeline = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        state = runtime.live_state()
        return {
            "status": "ok",
            "service": "online",
            "database": "online" if repo.healthy() else "offline",
            "model": "ready" if state.camera.status.value == "online" else "waiting",
            "source": state.camera.model_dump(mode="json"),
        }

    @app.get("/api/v1/cameras", response_model=list[CameraState])
    def cameras() -> list[CameraState]:
        return [runtime.live_state().camera]

    @app.get("/api/v1/cameras/{camera_id}", response_model=CameraState)
    def camera(camera_id: str) -> CameraState:
        _require_camera(camera_id, app_config)
        return runtime.live_state().camera

    @app.post("/api/v1/cameras/{camera_id}/start", response_model=CameraState)
    def start_camera(camera_id: str, selection: SourceSelection | None = None) -> CameraState:
        _require_camera(camera_id, app_config)
        if selection:
            runtime.select_source(selection)
        else:
            runtime.start()
        return runtime.live_state().camera

    @app.post("/api/v1/cameras/{camera_id}/stop", response_model=CameraState)
    def stop_camera(camera_id: str) -> CameraState:
        _require_camera(camera_id, app_config)
        runtime.stop()
        return runtime.live_state().camera

    @app.post("/api/v1/cameras/{camera_id}/reset", response_model=CameraState)
    def reset_camera(camera_id: str) -> CameraState:
        _require_camera(camera_id, app_config)
        runtime.reset()
        return runtime.live_state().camera

    @app.post("/api/v1/cameras/{camera_id}/overlays", response_model=dict[str, bool])
    def overlays(camera_id: str, enabled: bool = Query(...)) -> dict[str, bool]:
        _require_camera(camera_id, app_config)
        runtime.toggle_overlays(enabled)
        return {"enabled": enabled}

    @app.get("/api/v1/cameras/{camera_id}/snapshot")
    def snapshot(camera_id: str) -> Response:
        _require_camera(camera_id, app_config)
        jpeg = runtime.snapshot()
        if jpeg is None:
            raise HTTPException(status_code=503, detail="No frame is available yet")
        return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/cameras/{camera_id}/stream.mjpg")
    async def stream(camera_id: str) -> StreamingResponse:
        _require_camera(camera_id, app_config)

        async def frames() -> AsyncIterator[bytes]:
            while True:
                jpeg = runtime.snapshot()
                if jpeg:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                await asyncio.sleep(1 / app_config.camera.display_fps)

        return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.get("/api/v1/zones", response_model=list[ZoneConfig])
    def zones() -> list[ZoneConfig]:
        return app_config.zones

    @app.get("/api/v1/metrics/current", response_model=list[ZoneMetric])
    def current_metrics(camera_id: str | None = None) -> list[ZoneMetric]:
        if camera_id:
            _require_camera(camera_id, app_config)
        return runtime.live_state().metrics

    @app.get("/api/v1/metrics/summary", response_model=list[SummaryPoint])
    def metric_summary(
        zone_id: str | None = None, minutes: int = Query(30, ge=1, le=1440)
    ) -> list[SummaryPoint]:
        return repo.summary(zone_id=zone_id, minutes=minutes)

    @app.get("/api/v1/events", response_model=list[Event])
    def events(limit: int = Query(50, ge=1, le=500), event_type: str | None = None) -> list[Event]:
        return repo.recent_events(limit=limit, event_type=event_type)

    @app.post("/api/v1/events/{event_id}/feedback", response_model=Event)
    def event_feedback(event_id: str, request: FeedbackRequest) -> Event:
        event = repo.feedback(event_id, request.status, request.reason)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        return event

    @app.websocket("/ws/live")
    async def live(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                state = runtime.live_state()
                await websocket.send_json(
                    {
                        "type": "live_update",
                        "camera": state.camera.model_dump(mode="json"),
                        "metrics": [item.model_dump(mode="json") for item in state.metrics],
                        "tracks": [item.model_dump(mode="json") for item in state.tracks],
                        "events": [item.model_dump(mode="json") for item in state.latest_events],
                    }
                )
                await asyncio.sleep(0.5)
        except WebSocketDisconnect:
            return

    return app


def _require_camera(camera_id: str, config: AppConfig) -> None:
    if camera_id != config.camera.camera_id:
        raise HTTPException(status_code=404, detail="Camera not found")


app = create_app()

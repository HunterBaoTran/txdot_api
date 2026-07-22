# Architecture notes

## Runtime flow

```text
File loop / webcam
        |
  VideoSource adapter
        |
 bounded latest-frame processing
        |
PersonDetector -> MultiObjectTracker
        |          (ephemeral IDs)
        v
ZoneEngine -> EventEngine -> AnalyticsRepository -> SQLite
        |                                  |
        +----------> VideoPipeline <-------+
                         |
        REST / MJPEG / snapshot / WebSocket
                         |
                 React dashboard
```

`backend/app/video_sources.py`, `detectors.py`, `tracking.py`, `analytics.py`, `events.py`, and `repository.py` define the replaceable boundaries. The API never performs CV logic. WebSocket messages carry only normalized metadata; annotated frames use MJPEG and are never base64-encoded onto the event channel.

Zone definitions and their revision are persisted in SQLite. YAML provides the first seed only. The dashboard draws drafts on a canvas aligned to the contained video image, sends normalized coordinates through revision-checked CRUD endpoints, and the pipeline atomically reconfigures `ZoneEngine`. Unchanged zones retain in-process visit state; changed or deleted geometry invalidates only affected active visits. Historical event and metric rows are never cascaded when a zone is deleted.

The pipeline processes the latest decoded frame on a fixed display cadence and samples inference independently. OpenCV file reads rewind at EOF. Read/open failures close the adapter, update health, emit one deduplicated offline event for the incident, then retry without terminating FastAPI. There is no unbounded frame or message collection.

Dwell duration uses monotonic process time, while persisted timestamps use timezone-aware UTC. Entry and exit require configurable consecutive observations. A dwell threshold emits once per track/zone visit. Completed visits contribute to average dwell, and current visits contribute while active.

## Unity/VMS replacement path

An authorized Unity integration should add `RtspSource` or `VmsSource` implementing `VideoSource.open/read/close/fps`. Analytics, persistence, API contracts, and the dashboard do not change. Production work should add secret-backed source configuration, authentication, audit logs, VMS clip references, health telemetry, and a tenant/camera registry.

## Deferred production items

- exact Unity RTSP/ONVIF/VMS discovery, authentication, clip lookup, and callbacks
- OAuth/JWT, RBAC, tenant boundaries, public API rate limits, and audit trails
- PostgreSQL/time-series retention, migrations, backups, and HA
- edge buffering, GPU scheduling, cross-camera correlation, AWS managed services
- casino-specific model evaluation, labeled footage, and jurisdictional approvals
- custom anomaly/VLM stages; these must remain human-reviewed and neutral

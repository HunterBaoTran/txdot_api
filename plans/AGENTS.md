# Veratex Video Intelligence POC — Codex Guidance

## Mission

Build a convincing local, end-to-end proof of concept for Veratex that demonstrates continuous video ingestion, computer-vision inference, anonymous tracking, zone/seat analytics, event generation, a documented API, and a live dashboard. The POC must work before Unity Surveillance provides a production camera/VMS integration.

Read `VERATEX_CODEX_BRIEF.md` before planning or editing. Treat it as the product and architecture source of truth for the POC.

## Scope discipline

- This repository is the pre-MVP demonstration, not the complete 6–8 month enterprise rollout.
- Build one reliable vertical slice first: video source -> detection -> tracking -> zones -> metrics/events -> API/WebSocket -> dashboard.
- Use an adapter boundary for video input so a file loop or webcam can later be replaced by an authorized RTSP/ONVIF/VMS stream.
- Do not require Unity APIs, AWS, a casino camera, custom model training, facial recognition, biometric identification, or automated enforcement for the first runnable demo.
- Do not claim identity, cheating, theft, intent, demographic attributes, or regulatory conclusions from video.
- Keep people anonymous. Use ephemeral tracker IDs only.
- Do not scrape, copy, or bundle footage without clear reuse rights. Include synthetic or user-owned demo modes.

## Preferred POC stack

- Python 3.11+
- FastAPI REST API and WebSockets
- OpenCV/FFmpeg for capture and decoding
- Ultralytics YOLO person detection with ByteTrack (or an equivalent well-maintained tracker)
- SQLAlchemy with SQLite for local development; keep persistence interfaces portable to PostgreSQL
- React + TypeScript + Vite for the dashboard
- Recharts or an equivalent lightweight chart library
- Pytest for backend tests; Vitest/React Testing Library for frontend tests
- Docker Compose only after the native local workflow works

If the existing repository already establishes a coherent alternative, preserve it unless it blocks the required vertical slice.

## Required engineering behavior

- Inspect the repository before changing it; preserve unrelated user work.
- Plan before implementing substantial changes.
- Keep video-source, detector, tracker, analytics, event, persistence, and API concerns separated behind explicit interfaces.
- Put camera and zone configuration in data files or environment variables, not hardcoded inside inference logic.
- Use UTC timestamps internally and expose ISO 8601 timestamps.
- Include type hints, structured logging, clear errors, and deterministic unit tests.
- Never put raw image bytes on an event/message bus; pass metadata and a frame/clip reference.
- Do not store full video by default. Any debug snapshots must be optional, bounded by retention, and excluded from git.
- Avoid sending video or frames to external services unless the user explicitly approves it.
- Never commit credentials, camera URLs, tokens, personally identifying data, or licensed footage.

## Definition of done for the first vertical slice

- A user can select a webcam or local MP4; a file can loop to simulate a continuous live feed.
- The UI displays the annotated stream with stable anonymous track IDs and configured zones.
- The system calculates current occupancy, entries/exits, dwell time, and utilization per zone.
- The backend emits structured events and updates the dashboard without a page refresh.
- REST endpoints expose health, cameras, current metrics, recent events, and summaries.
- The demo continues through a temporary dropped frame or unavailable source and reports source health.
- Sample configuration, setup instructions, architecture notes, API examples, and demo steps exist.
- Backend tests cover zone membership, dwell-time accumulation, event thresholds, and API schemas.
- Relevant tests, linting, and type checks pass; Codex reports the exact commands run.

## Future-production alignment

The approved long-term direction is an AWS-managed hybrid architecture: RTSP/ONVIF or VMS tap, edge relay/buffering, Kinesis metadata streams, S3 frame references, SageMaker-hosted detection/anomaly models, event-triggered vision-language transcripts through Bedrock, Lambda/EventBridge aggregation, Timestream/OpenSearch storage, and a React/WebSocket dashboard secured with Cognito, KMS, IAM, PrivateLink, and CloudTrail. Preserve interfaces that make this migration possible, but do not provision that estate for the local POC unless explicitly requested.

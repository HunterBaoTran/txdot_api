# Veratex Video Intelligence POC

A local, end-to-end demonstration of continuous video ingestion, anonymous person tracking, configurable zone analytics, event persistence, a documented FastAPI/WebSocket API, and a live React dashboard.

The default demo is deterministic and rights-safe: the backend generates an MP4 containing synthetic people-like markers, loops it continuously, detects those markers, tracks them with ByteTrack, and calculates table/seat activity. No casino footage, camera, credentials, cloud service, or model download is required for that mode. User-owned MP4 and webcam modes switch to pretrained YOLO person detection plus the same ByteTrack adapter.

## What is included

- OpenCV `FileLoopSource` and `WebcamSource` behind a replaceable `VideoSource` contract
- rights-safe generated MP4 default; no recorded people or bundled licensed media
- Ultralytics YOLO person detection and anonymous Supervision ByteTrack tracking
- normalized polygon zones and a configurable six-seat table preset
- debounced occupancy, entries, exits, dwell, utilization, capacity, and source-health events
- SQLite persistence through a repository boundary portable to PostgreSQL
- FastAPI REST, OpenAPI, MJPEG stream, snapshot, controls, analyst feedback, and WebSocket updates
- React + TypeScript dashboard with annotated video, KPIs, source health, seats, trend chart, and event feed
- deterministic Pytest and Vitest coverage

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer and npm
- A webcam only if testing webcam mode

The first YOLO run downloads the official pretrained `yolo11n.pt` weight through Ultralytics. The deterministic default does not download a model. Model weights and generated video/database files are git-ignored.

## Clean setup (PowerShell)

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
npm --prefix frontend install
```

The backend generates `data/demo.mp4` at first startup. To create it explicitly:

```powershell
python -m app.demo_video
```

## Launch the finished demo

Open two PowerShell terminals from the repository root with the virtual environment active.

Terminal 1 — API and video pipeline:

```powershell
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Terminal 2 — dashboard:

```powershell
npm --prefix frontend run dev
```

Open <http://127.0.0.1:5173>. API docs are at <http://127.0.0.1:8000/docs>.

The generated MP4 loop starts automatically. Occupancy changes are deliberately staged throughout its 18-second cycle so entries, exits, dwell alerts, seat state, utilization, trends, and events can be demonstrated without external footage.

## Use a webcam or user-owned MP4

Choose **Webcam 0 + YOLO** in the dashboard and select **Start source**. If device index `0` is unavailable, the pipeline remains alive, marks the source offline, records a neutral `source_offline` event, and retries.

To use an authorized local MP4, edit `config/demo.yaml`:

```yaml
camera:
  source_type: file_loop
  source: C:/absolute/path/to/authorized-video.mp4
  detector: yolo
  loop: true
```

Restart the backend. Do not add private footage, model weights, or generated data to git.

## Configuration

`config/demo.yaml` contains the source, inference/display rates, reconnect policy, debounce settings, and normalized table/seat polygons. Coordinates are pairs in the `[0, 1]` range, so the preset scales with video resolution. Set `VERATEX_CONFIG` to use another YAML file and `VERATEX_DATABASE_URL` to select another SQLAlchemy database URL.

## Checks

```powershell
python -m pytest
python -m ruff check backend
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
```

## Troubleshooting

- **Snapshot says no frame:** wait one second and check `/health`; `source.last_error` contains the actionable cause.
- **Webcam is offline:** close other camera applications, verify OS camera permission, or try a different index in the API/config.
- **YOLO is slow:** lower `inference_fps` to 2–3. Display FPS and inference FPS are intentionally independent.
- **Model download fails:** use the generated demo until network access is available, or pre-place the official weight in the working directory.
- **Video codec cannot open:** install an OpenCV/FFmpeg build supporting that codec or transcode user-owned footage to H.264/MP4.
- **Dashboard is reconnecting:** verify the backend is on `127.0.0.1:8000`; the Vite proxy handles REST, MJPEG, and WebSocket routes.

## Privacy and limitations

Tracker IDs are ephemeral session-scoped labels, not identities. The POC performs no face recognition, biometric inference, demographic inference, intent classification, accusation, or automated enforcement. It stores metrics/events only and does not record full video. Human review is required. The synthetic detector is only for the generated demonstration; real sources use YOLO.

This is a single-camera local pre-MVP, without production authentication, tenant isolation, VMS clip linkage, HA, GPU scheduling, or regulatory controls. See [architecture notes](docs/ARCHITECTURE.md), [API examples](docs/API_EXAMPLES.md), and the [10-minute demo script](docs/DEMO_SCRIPT.md).


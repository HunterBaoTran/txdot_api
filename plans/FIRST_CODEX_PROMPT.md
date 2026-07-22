# First prompt to give Codex

Copy the prompt below into Codex after placing `AGENTS.md` and `VERATEX_CODEX_BRIEF.md` at the repository root.

---

We are starting the Veratex real-time video-intelligence proof of concept.

Read `AGENTS.md` and `VERATEX_CODEX_BRIEF.md` completely. Then inspect the repository and work in Plan mode first.

Goal: deliver the first runnable vertical slice for a client demonstration: a local MP4 that loops like a continuous live feed (plus webcam support where available) -> person detection -> anonymous ByteTrack tracking -> configurable polygon zones -> live occupancy, entries/exits, dwell time, and utilization -> FastAPI REST/WebSocket API -> React dashboard with annotated video, KPI cards, trend chart, source health, and recent events.

Important boundaries:

- This is a pre-MVP demo, not the complete AWS/Unity production platform.
- Do not block on Unity feeds, VMS APIs, AWS credentials, a casino dataset, custom anomaly training, a VLM, facial recognition, identity, or automated enforcement.
- Keep the video-source, detector, tracker, zone analytics, event, persistence, and delivery layers replaceable.
- Default to a deterministic local file-loop demo and do not download or commit questionable footage.
- Use neutral operational events only.
- Do not store full video by default or expose a camera stream publicly.

Before implementation, give me:

1. your repository assessment;
2. the proposed directory structure and component boundaries;
3. the exact first milestone and acceptance tests;
4. any true blocker requiring my decision.

If there is no blocker, continue without waiting: implement the first vertical slice, add tests and documentation, run the relevant checks, fix failures, and provide the exact commands to launch the backend and frontend and run the demo. Keep a short list of deferred production items rather than expanding scope.

Done means the clean-checkout workflow and acceptance criteria in `VERATEX_CODEX_BRIEF.md` are satisfied, or you report a specific verified blocker with evidence.

---

## Useful follow-up prompt after the first slice works

Review the completed vertical slice against every acceptance criterion in `VERATEX_CODEX_BRIEF.md`. Fix verified gaps. Then add a configurable six-seat table preset, deterministic demo events, an analyst acknowledge/dismiss feedback action, and a 10-minute client demo script. Run tests and a 30-minute file-loop soak test, report CPU/GPU usage and observed latency, and do not add AWS or Unity dependencies yet.

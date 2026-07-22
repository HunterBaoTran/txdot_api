# 10-minute client demo script

## 0:00–1:00 — Frame the POC

Explain that this is a local pre-MVP demonstrating the complete analytics path before Unity provides an authorized feed. The source is synthetic and rights-safe; IDs are anonymous and session-scoped.

## 1:00–3:00 — Show the continuous feed

Open the dashboard and point out the looping video, polygon table/seat zones, and stable anonymous labels. Toggle overlays off and on. Note that display and inference rates are decoupled to preserve low latency.

## 3:00–5:00 — Show operational value

Watch people enter the table. Call out current occupancy, occupied seats, utilization, entries/exits, average dwell, and the live seat strip. Explain normalized zone configuration and the six-seat preset.

## 5:00–6:30 — Draw a custom zone

Select **Edit zones**, choose **New zone**, and draw a polygon over part of the table. Name it, set its type and capacity, and save it. Show that the backend annotation and live metrics adopt the new zone without restarting the source. Mention that the six-seat layout is now an optional editable preset.

## 6:30–7:30 — Show history and API

Point to the zone-aware recent feed and trend chart, then open `/docs`. Show health, cameras, zone CRUD/revisions, current metrics, summaries, and recent events. Emphasize UTC contracts and metadata-only WebSockets.

## 7:30–8:30 — Show resilience

Select webcam mode on a system without a webcam, or temporarily rename a user-owned source. The API stays up, reports the source offline with a clear error, emits one neutral health event, and retries. Return to Generated MP4 loop.

## 8:30–9:30 — Explain the integration boundary

Use the architecture diagram to show where an authorized Unity RTSP/VMS adapter replaces the file/webcam adapter. No analytics or dashboard rewrite is required, and the incumbent VMS remains the evidentiary system of record.

## 9:30–10:00 — Close with boundaries

Reiterate: no facial recognition, identity, demographic inference, intent claims, automated enforcement, default video recording, or cloud dependency. Human review remains mandatory. Then name the production decisions intentionally deferred in `ARCHITECTURE.md`.

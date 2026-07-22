# Next Steps — Drawable Zones

**Date:** July 22, 2026  
**Goal:** Replace the demo’s fixed polygon-only workflow with an interactive dashboard editor where an operator can draw, edit, save, and activate zones directly over the live camera view.

## Desired user experience

1. Open a camera and select **Edit zones**.
2. Choose a zone type: table, seat, queue, dealer, or restricted area.
3. Click on the video to place polygon vertices.
4. Close the polygon by clicking the first point or selecting **Finish zone**.
5. Enter the zone name, capacity, dwell threshold, and optional alert behavior.
6. Preview the zone, then save or cancel it.
7. Drag existing vertices to reshape a zone, or rename, disable, duplicate, and delete it.
8. See analytics begin using the saved geometry without restarting the application.

The six-seat table configuration should remain available as an optional **Load preset** action, but it should no longer be the only way to define zones.

## Product behavior

- Drawing happens on a transparent canvas aligned exactly with the displayed video.
- Pointer coordinates are converted to normalized `[0, 1]` coordinates before saving, so zones remain correct at different stream resolutions and dashboard sizes.
- A polygon requires at least three valid, non-duplicated points.
- The editor visibly distinguishes draft, selected, active, disabled, and invalid zones.
- Editing mode pauses drawing interactions from affecting normal dashboard controls; video and analytics may continue running.
- Unsaved edits show a clear dirty-state warning before the user leaves editing mode.
- Keyboard support includes `Escape` to cancel, `Enter` to finish, and `Delete` to remove a selected vertex or zone after confirmation.
- Touch and mouse input should both work.
- Saving a new configuration should be atomic: the pipeline continues using the last valid configuration until the new revision validates and commits.

## Proposed architecture

### Frontend

Add a `ZoneEditor` feature containing:

- `VideoCoordinateMapper` for converting rendered video coordinates to normalized source coordinates while accounting for letterboxing;
- `PolygonCanvas` for point placement, edges, vertex handles, selection, and drag editing;
- `ZonePropertiesPanel` for name, type, capacity, dwell threshold, color, and enabled state;
- editor state with explicit `viewing`, `drawing`, `editing`, `saving`, and `error` modes;
- preset loading and draft validation;
- API calls for zone CRUD and configuration activation.

Use an HTML canvas or positioned HTML overlay rather than baking zones into the MJPEG frame while editing. After saving, the backend annotator remains responsible for the authoritative stream overlay.

### Backend

Extend the zone boundary with:

- SQLite-backed zone configuration and revision records;
- validation for unique IDs, supported types, capacity, thresholds, normalized coordinates, polygon area, and self-intersection;
- repository methods for listing, creating, updating, disabling, and deleting zones;
- atomic `ZoneEngine` configuration replacement under the pipeline lock;
- a configuration revision number in REST and WebSocket messages;
- an audit-friendly timestamp for each zone change without storing video or user identity.

Suggested endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/cameras/{camera_id}/zones` | List active and disabled zones for a camera |
| `POST` | `/api/v1/cameras/{camera_id}/zones` | Validate and create a drawn zone |
| `PUT` | `/api/v1/cameras/{camera_id}/zones/{zone_id}` | Replace zone geometry and properties |
| `DELETE` | `/api/v1/cameras/{camera_id}/zones/{zone_id}` | Remove a zone after confirmation |
| `POST` | `/api/v1/cameras/{camera_id}/zones/presets/{preset_id}` | Load a preset as an editable draft or saved configuration |

Mutating requests should include the client’s last-seen revision. Return `409 Conflict` if another update has already produced a newer configuration.

## Persistence and migration

- Introduce `ZoneRow` and `ZoneRevisionRow` SQLAlchemy models.
- Seed SQLite from `config/demo.yaml` only when a camera has no persisted zones.
- Treat YAML presets as templates, not as the runtime source of truth after the first saved edit.
- Store normalized polygon points as validated JSON for the POC; a future PostgreSQL implementation may use PostGIS.
- Preserve existing zone IDs where possible so historical metrics and events remain interpretable.
- Prevent deletion of a zone from deleting its historical events or metrics.

## Implementation sequence

### Milestone 1 — Editable overlay prototype

- Render the current zones over the video in a browser-aligned overlay.
- Draw a polygon using mouse and touch input.
- Move and remove vertices.
- Convert coordinates correctly when the video is letterboxed or resized.
- Keep changes in frontend draft state only.

### Milestone 2 — Zone API and persistence

- Add database models and repository methods.
- Add CRUD endpoints, validation, revisions, and API examples.
- Seed the current six-seat YAML preset on an empty database.
- Add deterministic repository and API tests.

### Milestone 3 — Live analytics activation

- Apply a saved revision to `ZoneEngine` without restarting the camera.
- Clear only invalidated in-progress visit state; retain cumulative persisted history.
- Broadcast the new zone revision over WebSocket.
- Update authoritative annotations and metrics for the new polygons.

### Milestone 4 — Complete operator workflow

- Add zone properties, enable/disable, duplication, deletion confirmation, and preset loading.
- Add dirty-state and conflict handling.
- Add keyboard accessibility and responsive/touch behavior.
- Add a short drawable-zone section to the client demo script.

## Acceptance tests

- A user can draw and save a polygon with three or more points over the live feed.
- Saved coordinates remain aligned after resizing the browser and after restarting the backend.
- Letterboxed video coordinates map to the source frame accurately.
- Invalid, tiny, duplicate-point, out-of-range, and self-intersecting polygons are rejected with clear messages.
- A user can drag a vertex, save the change, and see the backend annotation update without restarting.
- Analytics use the new polygon on the next inference cycle.
- Concurrent stale edits receive `409 Conflict` and do not overwrite newer work.
- Loading the six-seat preset creates editable zones rather than hardcoded inference behavior.
- Deleting a zone leaves its historical events and metrics intact.
- Frontend tests cover drawing, editing, cancellation, coordinate conversion, and error states.
- Backend tests cover CRUD schemas, geometry validation, revisions, persistence, and atomic runtime reload.

## Decisions and constraints

- Keep zone editing local and unauthenticated for this POC; production editing will require RBAC and audit attribution.
- Do not store frames or video as part of zone configuration.
- Do not infer zones automatically in this milestone.
- Do not introduce Unity/VMS dependencies; drawable zones operate against any existing `VideoSource` adapter.
- Continue using neutral, anonymous operational analytics only.

## Definition of done

This next step is complete when a new user can launch the deterministic demo, draw a custom table or seat zone in the dashboard, save it, immediately see occupancy and events calculated against it, restart the application, and find the same zone restored and correctly aligned.

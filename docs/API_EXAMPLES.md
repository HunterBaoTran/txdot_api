# API examples

OpenAPI is served at `http://127.0.0.1:8000/docs`. All durable timestamps are ISO 8601 UTC.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/cameras
Invoke-RestMethod http://127.0.0.1:8000/api/v1/zones
Invoke-RestMethod http://127.0.0.1:8000/api/v1/metrics/current
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/metrics/summary?zone_id=table-1&minutes=30'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/events?limit=20'
```

Control the configured camera:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/cameras/demo-table-01/stop
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/cameras/demo-table-01/start
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/cameras/demo-table-01/reset
```

Switch to webcam 0 with YOLO:

```powershell
$body = @{ source_type = 'webcam'; source = 0; detector = 'yolo' } | ConvertTo-Json
Invoke-RestMethod -Method Post -ContentType application/json -Body $body http://127.0.0.1:8000/api/v1/cameras/demo-table-01/start
```

Acknowledge an event:

```powershell
$body = @{ status = 'acknowledged'; reason = 'Reviewed during demo' } | ConvertTo-Json
Invoke-RestMethod -Method Post -ContentType application/json -Body $body http://127.0.0.1:8000/api/v1/events/EVENT_ID/feedback
```

`ws://127.0.0.1:8000/ws/live` emits `live_update` objects every 500 ms with camera health, current metrics, anonymous tracks, and newly generated events. Frames remain on `/api/v1/cameras/{camera_id}/stream.mjpg`.


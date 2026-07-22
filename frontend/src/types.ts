export type SourceStatus = 'stopped' | 'starting' | 'online' | 'degraded' | 'offline'

export interface CameraState {
  camera_id: string
  name: string
  source_type: string
  status: SourceStatus
  fps_input: number
  fps_inference: number
  last_frame_at: string | null
  processing_latency_ms: number
  dropped_frames: number
  last_error: string | null
}

export interface ZoneMetric {
  camera_id: string
  zone_id: string
  timestamp: string
  occupancy: number
  capacity: number
  utilization_pct: number
  entries_total: number
  exits_total: number
  average_dwell_seconds: number
}

export interface EventItem {
  event_id: string
  camera_id: string
  zone_id: string | null
  event_type: string
  severity: 'info' | 'warning' | 'critical'
  occurred_at: string
  track_id: number | null
  attributes: Record<string, number | string>
  feedback_status: string | null
}

export interface SummaryPoint {
  timestamp: string
  occupancy: number
  utilization_pct: number
}

export interface LiveUpdate {
  type: 'live_update'
  camera: CameraState
  metrics: ZoneMetric[]
  events: EventItem[]
}


import type { EventItem, SummaryPoint } from './types'

export const API_BASE = import.meta.env.VITE_API_BASE ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export function streamUrl(cameraId: string): string {
  return `${API_BASE}/api/v1/cameras/${cameraId}/stream.mjpg`
}

export function websocketUrl(): string {
  const base = API_BASE || window.location.origin
  return `${base.replace(/^http/, 'ws')}/ws/live`
}

export const api = {
  events: () => request<EventItem[]>('/api/v1/events?limit=30'),
  summary: (zoneId = 'table-1') =>
    request<SummaryPoint[]>(`/api/v1/metrics/summary?zone_id=${zoneId}&minutes=30`),
  start: (cameraId: string, sourceType: 'file_loop' | 'webcam', source: string | number, detector: 'synthetic' | 'yolo') =>
    request(`/api/v1/cameras/${cameraId}/start`, {
      method: 'POST',
      body: JSON.stringify({ source_type: sourceType, source, detector }),
    }),
  stop: (cameraId: string) => request(`/api/v1/cameras/${cameraId}/stop`, { method: 'POST' }),
  reset: (cameraId: string) => request(`/api/v1/cameras/${cameraId}/reset`, { method: 'POST' }),
  overlays: (cameraId: string, enabled: boolean) =>
    request(`/api/v1/cameras/${cameraId}/overlays?enabled=${enabled}`, { method: 'POST' }),
  feedback: (eventId: string, status: 'acknowledged' | 'dismissed') =>
    request<EventItem>(`/api/v1/events/${eventId}/feedback`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    }),
}


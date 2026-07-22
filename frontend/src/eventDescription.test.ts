import { describe, expect, it } from 'vitest'
import { eventDescription } from './eventDescription'
import type { EventItem, ZoneConfig } from './types'

const zone: ZoneConfig = {
  zone_id: 'custom-queue',
  name: 'North Lobby Queue',
  zone_type: 'queue',
  polygon_normalized: [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4]],
  capacity: 4,
  dwell_alert_seconds: 30,
  enabled: true,
  color: '#e1a44e',
}

function event(event_type: string): EventItem {
  return {
    event_id: 'event-1', camera_id: 'camera', zone_id: zone.zone_id, event_type,
    severity: 'info', occurred_at: '2026-07-22T12:00:00Z', track_id: 9,
    attributes: { occupancy: 1, capacity: 4 }, feedback_status: null,
  }
}

describe('event descriptions', () => {
  it('uses the current custom zone name for entries and exits', () => {
    expect(eventDescription(event('zone_entered'), [zone])).toBe('Anonymous person #9 entered North Lobby Queue')
    expect(eventDescription({ ...event('zone_exited'), attributes: { dwell_seconds: 18 } }, [zone]))
      .toBe('Anonymous person #9 exited North Lobby Queue after 18s')
  })
})


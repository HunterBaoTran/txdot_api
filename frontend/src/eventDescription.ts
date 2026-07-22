import type { EventItem, ZoneConfig } from './types'

export function formatEventName(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function eventDescription(event: EventItem, zones: ZoneConfig[]) {
  const zone = zones.find((item) => item.zone_id === event.zone_id)
  const zoneName = String(event.attributes.zone_name ?? zone?.name ?? event.zone_id ?? 'Camera')
  const person = event.track_id === null ? 'The zone' : `Anonymous person #${event.track_id}`
  const dwell = event.attributes.dwell_seconds === undefined
    ? ''
    : ` after ${Math.round(Number(event.attributes.dwell_seconds))}s`
  const messages: Record<string, string> = {
    zone_entered: `${person} entered ${zoneName}`,
    zone_exited: `${person} exited ${zoneName}${dwell}`,
    zone_occupied: `${zoneName} became occupied`,
    zone_vacant: `${zoneName} became vacant`,
    capacity_reached: `${zoneName} reached its capacity of ${event.attributes.capacity ?? zone?.capacity ?? '—'}`,
    dwell_threshold_exceeded: `${person} exceeded the dwell threshold in ${zoneName}`,
    source_offline: 'The camera source went offline',
  }
  return messages[event.event_type] ?? `${formatEventName(event.event_type)} in ${zoneName}`
}


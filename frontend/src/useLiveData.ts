import { useCallback, useEffect, useRef, useState } from 'react'
import { api, websocketUrl } from './api'
import type { EventItem, LiveUpdate, SummaryPoint, ZoneCollection, ZoneConfig } from './types'

const CAMERA_ID = 'demo-table-01'

export function useLiveData() {
  const [live, setLive] = useState<LiveUpdate | null>(null)
  const [connected, setConnected] = useState(false)
  const [history, setHistory] = useState<SummaryPoint[]>([])
  const [archivedEvents, setArchivedEvents] = useState<EventItem[]>([])
  const [zones, setZones] = useState<ZoneConfig[]>([])
  const [zoneRevision, setZoneRevision] = useState(0)
  const zoneRevisionRef = useRef(0)
  const retry = useRef<number | undefined>(undefined)

  const applyZoneCollection = useCallback((collection: ZoneCollection) => {
    if ((collection.revision ?? 0) < zoneRevisionRef.current) return
    zoneRevisionRef.current = collection.revision ?? 0
    setZones(collection.zones ?? [])
    setZoneRevision(collection.revision ?? 0)
  }, [])

  useEffect(() => {
    let disposed = false
    let socket: WebSocket | null = null
    const connect = () => {
      socket = new WebSocket(websocketUrl())
      socket.onopen = () => setConnected(true)
      socket.onmessage = (message) => {
        const update = JSON.parse(message.data) as LiveUpdate
        setLive(update)
        applyZoneCollection({
          camera_id: update.camera.camera_id,
          revision: update.zone_revision,
          updated_at: update.camera.last_frame_at ?? new Date().toISOString(),
          zones: update.zones,
        })
      }
      socket.onclose = () => {
        setConnected(false)
        if (!disposed) retry.current = window.setTimeout(connect, 1500)
      }
      socket.onerror = () => socket?.close()
    }
    connect()
    void Promise.all([api.events(), api.zones(CAMERA_ID)]).then(([events, collection]) => {
      if (!disposed) {
        setArchivedEvents(events)
        applyZoneCollection(collection)
      }
    }).catch(() => undefined)
    return () => {
      disposed = true
      window.clearTimeout(retry.current)
      socket?.close()
    }
  }, [applyZoneCollection])

  useEffect(() => {
    const zoneId = zones.find((zone) => zone.enabled && zone.zone_type === 'table')?.zone_id
      ?? zones.find((zone) => zone.enabled)?.zone_id
    if (!zoneId) {
      return
    }
    const refresh = () => void api.summary(zoneId).then(setHistory).catch(() => undefined)
    refresh()
    const poll = window.setInterval(refresh, 5000)
    return () => window.clearInterval(poll)
  }, [zones])

  const events = [...(live?.events ?? []), ...archivedEvents].filter(
    (item, index, items) => items.findIndex((other) => other.event_id === item.event_id) === index,
  )
  const visibleHistory = zones.some((zone) => zone.enabled) ? history : []
  return { live, connected, history: visibleHistory, events, zones, zoneRevision, applyZoneCollection }
}

import { useEffect, useRef, useState } from 'react'
import { api, websocketUrl } from './api'
import type { EventItem, LiveUpdate, SummaryPoint } from './types'

export function useLiveData() {
  const [live, setLive] = useState<LiveUpdate | null>(null)
  const [connected, setConnected] = useState(false)
  const [history, setHistory] = useState<SummaryPoint[]>([])
  const [archivedEvents, setArchivedEvents] = useState<EventItem[]>([])
  const retry = useRef<number | undefined>(undefined)

  useEffect(() => {
    let disposed = false
    let socket: WebSocket | null = null
    const connect = () => {
      socket = new WebSocket(websocketUrl())
      socket.onopen = () => setConnected(true)
      socket.onmessage = (message) => setLive(JSON.parse(message.data) as LiveUpdate)
      socket.onclose = () => {
        setConnected(false)
        if (!disposed) retry.current = window.setTimeout(connect, 1500)
      }
      socket.onerror = () => socket?.close()
    }
    connect()
    void Promise.all([api.summary(), api.events()]).then(([points, events]) => {
      if (!disposed) {
        setHistory(points)
        setArchivedEvents(events)
      }
    }).catch(() => undefined)
    const poll = window.setInterval(() => {
      void api.summary().then(setHistory).catch(() => undefined)
    }, 5000)
    return () => {
      disposed = true
      window.clearTimeout(retry.current)
      window.clearInterval(poll)
      socket?.close()
    }
  }, [])

  const events = [...(live?.events ?? []), ...archivedEvents].filter(
    (item, index, items) => items.findIndex((other) => other.event_id === item.event_id) === index,
  )
  return { live, connected, history, events, setArchivedEvents }
}


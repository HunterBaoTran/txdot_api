import { useEffect, useRef } from 'react'
import type { ZoneConfig } from './types'
import { containedMediaBounds, displayToNormalized, normalizedToDisplay } from './videoCoordinates'

const TYPE_COLORS: Record<ZoneConfig['zone_type'], string> = {
  table: '#56d7b0',
  seat: '#ff9a6b',
  queue: '#e1a44e',
  dealer: '#bc70e1',
  restricted: '#ef5c5c',
}

interface PolygonCanvasProps {
  image: HTMLImageElement | null
  zones: ZoneConfig[]
  draft: ZoneConfig | null
  mode: 'viewing' | 'drawing' | 'editing'
  onAddPoint: (point: [number, number]) => void
  onMovePoint: (index: number, point: [number, number]) => void
  onFinish: () => void
}

export function PolygonCanvas({ image, zones, draft, mode, onAddPoint, onMovePoint, onFinish }: PolygonCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const draggingVertex = useRef<number | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const draw = () => {
      const rect = canvas.getBoundingClientRect()
      const ratio = window.devicePixelRatio || 1
      canvas.width = Math.max(1, Math.round(rect.width * ratio))
      canvas.height = Math.max(1, Math.round(rect.height * ratio))
      const context = canvas.getContext('2d')
      if (!context) return
      context.scale(ratio, ratio)
      context.clearRect(0, 0, rect.width, rect.height)
      const bounds = containedMediaBounds(rect.width, rect.height, image?.naturalWidth ?? 16, image?.naturalHeight ?? 9)
      const visible = zones.filter((zone) => zone.zone_id !== draft?.zone_id)
      for (const zone of visible) drawZone(context, zone, bounds, false)
      if (draft) drawZone(context, draft, bounds, true)
    }
    draw()
    const observer = new ResizeObserver(draw)
    observer.observe(canvas)
    image?.addEventListener('load', draw)
    return () => {
      observer.disconnect()
      image?.removeEventListener('load', draw)
    }
  }, [draft, image, zones])

  function eventPoint(event: React.PointerEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current
    if (!canvas) return null
    const rect = canvas.getBoundingClientRect()
    const bounds = containedMediaBounds(rect.width, rect.height, image?.naturalWidth ?? 16, image?.naturalHeight ?? 9)
    return displayToNormalized(event.clientX - rect.left, event.clientY - rect.top, bounds)
  }

  function nearestVertex(event: React.PointerEvent<HTMLCanvasElement>) {
    if (!draft) return null
    const canvas = canvasRef.current
    if (!canvas) return null
    const rect = canvas.getBoundingClientRect()
    const bounds = containedMediaBounds(rect.width, rect.height, image?.naturalWidth ?? 16, image?.naturalHeight ?? 9)
    const pointer = [event.clientX - rect.left, event.clientY - rect.top]
    const index = draft.polygon_normalized.findIndex((point) => {
      const shown = normalizedToDisplay(point, bounds)
      return Math.hypot(shown[0] - pointer[0], shown[1] - pointer[1]) <= 14
    })
    return index >= 0 ? index : null
  }

  function pointerDown(event: React.PointerEvent<HTMLCanvasElement>) {
    if (!draft || mode === 'viewing') return
    if (mode === 'editing') {
      draggingVertex.current = nearestVertex(event)
      if (draggingVertex.current !== null) event.currentTarget.setPointerCapture(event.pointerId)
      return
    }
    const first = nearestVertex(event)
    if (first === 0 && draft.polygon_normalized.length >= 3) {
      onFinish()
      return
    }
    const point = eventPoint(event)
    if (point) onAddPoint(point)
  }

  function pointerMove(event: React.PointerEvent<HTMLCanvasElement>) {
    if (draggingVertex.current === null) return
    const point = eventPoint(event)
    if (point) onMovePoint(draggingVertex.current, point)
  }

  return (
    <canvas
      ref={canvasRef}
      className={`polygon-canvas ${mode}`}
      aria-label="Drawable zone overlay"
      onPointerDown={pointerDown}
      onPointerMove={pointerMove}
      onPointerUp={() => { draggingVertex.current = null }}
      onPointerCancel={() => { draggingVertex.current = null }}
    />
  )
}

function drawZone(
  context: CanvasRenderingContext2D,
  zone: ZoneConfig,
  bounds: { x: number; y: number; width: number; height: number },
  selected: boolean,
) {
  const points = zone.polygon_normalized.map((point) => normalizedToDisplay(point, bounds))
  if (points.length === 0) return
  const color = zone.color ?? TYPE_COLORS[zone.zone_type]
  context.save()
  context.beginPath()
  context.moveTo(points[0][0], points[0][1])
  for (const point of points.slice(1)) context.lineTo(point[0], point[1])
  if (points.length >= 3) context.closePath()
  context.fillStyle = `${color}${selected ? '36' : '20'}`
  context.strokeStyle = zone.enabled ? color : '#65727b'
  context.lineWidth = selected ? 3 : 1.5
  context.setLineDash(zone.enabled ? [] : [6, 5])
  if (points.length >= 3) context.fill()
  context.stroke()
  context.setLineDash([])
  context.font = '500 11px Manrope, sans-serif'
  context.fillStyle = color
  context.fillText(zone.name, points[0][0] + 7, points[0][1] - 8)
  if (selected) {
    for (const [index, point] of points.entries()) {
      context.beginPath()
      context.arc(point[0], point[1], index === 0 ? 6 : 5, 0, Math.PI * 2)
      context.fillStyle = index === 0 ? '#ffffff' : color
      context.fill()
      context.strokeStyle = '#07110e'
      context.lineWidth = 2
      context.stroke()
    }
  }
  context.restore()
}


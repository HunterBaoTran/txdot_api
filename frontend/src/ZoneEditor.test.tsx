import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import type { ZoneCollection, ZoneConfig } from './types'
import { ZoneEditor } from './ZoneEditor'

const zone: ZoneConfig = {
  zone_id: 'queue-1', name: 'Guest Queue', zone_type: 'queue',
  polygon_normalized: [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4]],
  capacity: 4, dwell_alert_seconds: 30, enabled: true, color: '#e1a44e',
}

function collection(zones: ZoneConfig[], revision = 2): ZoneCollection {
  return { camera_id: 'camera', revision, updated_at: '2026-07-22T12:00:00Z', zones }
}

function renderEditor(zones: ZoneConfig[] = []) {
  const overlayHost = document.createElement('div')
  document.body.appendChild(overlayHost)
  const onChange = vi.fn()
  render(
    <ZoneEditor
      cameraId="camera" image={null} overlayHost={overlayHost} zones={zones}
      revision={1} open onClose={vi.fn()} onChange={onChange}
    />,
  )
  return { overlayHost, onChange }
}

describe('ZoneEditor', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      scale: vi.fn(), clearRect: vi.fn(), save: vi.fn(), restore: vi.fn(),
      beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(), closePath: vi.fn(),
      fill: vi.fn(), stroke: vi.fn(), setLineDash: vi.fn(), fillText: vi.fn(), arc: vi.fn(),
    } as unknown as CanvasRenderingContext2D)
    vi.spyOn(HTMLCanvasElement.prototype, 'getBoundingClientRect').mockReturnValue({
      x: 0, y: 0, left: 0, top: 0, right: 960, bottom: 540, width: 960, height: 540,
      toJSON: () => ({}),
    })
    Object.defineProperty(HTMLCanvasElement.prototype, 'setPointerCapture', {
      configurable: true, value: vi.fn(),
    })
  })

  it('draws, saves, and cancels a new polygon', async () => {
    const create = vi.spyOn(api, 'createZone').mockResolvedValue(collection([zone]))
    const { overlayHost, onChange } = renderEditor()
    fireEvent.click(screen.getByRole('button', { name: 'New zone' }))
    const canvas = overlayHost.querySelector('canvas')!
    fireEvent.pointerDown(canvas, { clientX: 100, clientY: 100 })
    fireEvent.pointerDown(canvas, { clientX: 400, clientY: 100 })
    fireEvent.pointerDown(canvas, { clientX: 400, clientY: 350 })
    expect(screen.getByText('3 points')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Save zone' }))
    await waitFor(() => expect(create).toHaveBeenCalled())
    expect(onChange).toHaveBeenCalledWith(collection([zone]))

    fireEvent.click(screen.getByRole('button', { name: 'New zone' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByText('Select a zone or start a new one.')).toBeInTheDocument()
  })

  it('edits an existing zone and surfaces API validation errors', async () => {
    const update = vi.spyOn(api, 'updateZone')
      .mockRejectedValueOnce(new Error('{"detail":"polygon cannot intersect itself"}'))
      .mockResolvedValueOnce(collection([{ ...zone, name: 'VIP Queue' }]))
    renderEditor([zone])
    fireEvent.click(screen.getByRole('button', { name: /Guest Queue/i }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'VIP Queue' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save zone' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('polygon cannot intersect itself')
    fireEvent.click(screen.getByRole('button', { name: 'Save zone' }))
    await waitFor(() => expect(update).toHaveBeenCalledTimes(2))
  })
})

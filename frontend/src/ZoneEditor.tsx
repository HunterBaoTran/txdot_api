import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from './api'
import { PolygonCanvas } from './PolygonCanvas'
import type { ZoneCollection, ZoneConfig, ZoneType } from './types'
import { movePolygonVertex } from './videoCoordinates'

const COLORS: Record<ZoneType, string> = {
  table: '#56d7b0',
  seat: '#ff9a6b',
  queue: '#e1a44e',
  dealer: '#bc70e1',
  restricted: '#ef5c5c',
}

interface ZoneEditorProps {
  cameraId: string
  image: HTMLImageElement | null
  overlayHost: HTMLElement | null
  zones: ZoneConfig[]
  revision: number
  open: boolean
  onClose: () => void
  onChange: (collection: ZoneCollection) => void
}

export function ZoneEditor({ cameraId, image, overlayHost, zones, revision, open, onClose, onChange }: ZoneEditorProps) {
  const [draft, setDraft] = useState<ZoneConfig | null>(null)
  const [original, setOriginal] = useState<ZoneConfig | null>(null)
  const [mode, setMode] = useState<'viewing' | 'drawing' | 'editing'>('viewing')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(original), [draft, original])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.matches('input, select, textarea')) return
      if (event.key === 'Escape') cancelDraft()
      if (event.key === 'Enter' && mode === 'drawing' && (draft?.polygon_normalized.length ?? 0) >= 3) {
        setMode('editing')
      }
      if ((event.key === 'Delete' || event.key === 'Backspace') && draft?.polygon_normalized.length) {
        setDraft({ ...draft, polygon_normalized: draft.polygon_normalized.slice(0, -1) })
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [draft, mode, open])

  if (!open) return null

  function beginNew() {
    const zone: ZoneConfig = {
      zone_id: `zone-${Date.now().toString(36)}`,
      name: `Zone ${zones.length + 1}`,
      zone_type: 'table',
      polygon_normalized: [],
      capacity: 6,
      dwell_alert_seconds: 60,
      enabled: true,
      color: COLORS.table,
    }
    setOriginal(null)
    setDraft(zone)
    setMode('drawing')
    setError(null)
  }

  function edit(zone: ZoneConfig) {
    setOriginal(structuredClone(zone))
    setDraft(structuredClone(zone))
    setMode('editing')
    setError(null)
  }

  function cancelDraft() {
    setDraft(null)
    setOriginal(null)
    setMode('viewing')
    setError(null)
  }

  function closeEditor() {
    if (dirty && !window.confirm('Discard unsaved zone changes?')) return
    cancelDraft()
    onClose()
  }

  async function save() {
    if (!draft || draft.polygon_normalized.length < 3) {
      setError('Place at least three points before saving this zone.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const collection = original
        ? await api.updateZone(cameraId, draft, revision)
        : await api.createZone(cameraId, draft, revision)
      onChange(collection)
      cancelDraft()
    } catch (reason) {
      setError(readError(reason))
    } finally {
      setBusy(false)
    }
  }

  async function remove(zone: ZoneConfig) {
    if (!window.confirm(`Delete ${zone.name}? Historical events and metrics will be retained.`)) return
    setBusy(true)
    try {
      onChange(await api.deleteZone(cameraId, zone.zone_id, revision))
      if (draft?.zone_id === zone.zone_id) cancelDraft()
    } catch (reason) {
      setError(readError(reason))
    } finally {
      setBusy(false)
    }
  }

  function duplicate(zone: ZoneConfig) {
    const copy: ZoneConfig = {
      ...structuredClone(zone),
      zone_id: `zone-${Date.now().toString(36)}`,
      name: `${zone.name} copy`,
      polygon_normalized: zone.polygon_normalized.map(([x, y]) => [Math.min(.98, x + .02), Math.min(.98, y + .02)]),
    }
    setOriginal(null)
    setDraft(copy)
    setMode('editing')
    setError(null)
  }

  async function loadPreset() {
    if (!window.confirm('Replace the current zones with the editable six-seat table preset?')) return
    setBusy(true)
    try {
      onChange(await api.loadPreset(cameraId, revision))
      cancelDraft()
    } catch (reason) {
      setError(readError(reason))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {overlayHost && createPortal(<PolygonCanvas
        image={image}
        zones={zones}
        draft={draft}
        mode={mode}
        onAddPoint={(point) => draft && setDraft({ ...draft, polygon_normalized: [...draft.polygon_normalized, point] })}
        onMovePoint={(index, point) => draft && setDraft({ ...draft, polygon_normalized: movePolygonVertex(draft.polygon_normalized, index, point) })}
        onFinish={() => setMode('editing')}
      />, overlayHost)}
      <section className="zone-editor-panel" aria-label="Zone editor">
        <div className="zone-editor-heading">
          <div><span className="eyebrow">ZONE CONFIGURATION · REV {revision}</span><h3>Draw and manage zones</h3></div>
          <div className="zone-editor-actions">
            <button onClick={beginNew} disabled={busy}>New zone</button>
            <button onClick={loadPreset} disabled={busy}>Load six-seat preset</button>
            <button onClick={closeEditor}>Done</button>
          </div>
        </div>
        <div className="zone-editor-body">
          <div className="zone-list">
            {zones.length === 0 && <p className="empty">No zones yet. Draw the first zone over the video.</p>}
            {zones.map((zone) => (
              <article className={draft?.zone_id === zone.zone_id ? 'zone-list-row selected' : 'zone-list-row'} key={zone.zone_id}>
                <span className="zone-swatch" style={{ background: zone.color ?? COLORS[zone.zone_type] }} />
                <button className="zone-select" onClick={() => edit(zone)}><strong>{zone.name}</strong><small>{zone.zone_type} · {zone.polygon_normalized.length} points · {zone.enabled ? 'active' : 'disabled'}</small></button>
                <button onClick={() => duplicate(zone)}>Duplicate</button>
                <button className="danger" onClick={() => void remove(zone)}>Delete</button>
              </article>
            ))}
          </div>
          <div className="zone-properties">
            {!draft && <div className="zone-instructions"><strong>Select a zone or start a new one.</strong><span>For a new zone, click around the video to place points. Click the first point or press Enter to finish.</span></div>}
            {draft && (
              <>
                <label>Name<input value={draft.name} maxLength={80} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
                <div className="zone-field-row">
                  <label>Type<select value={draft.zone_type} onChange={(event) => { const zone_type = event.target.value as ZoneType; setDraft({ ...draft, zone_type, color: COLORS[zone_type], capacity: zone_type === 'seat' ? 1 : draft.capacity }) }}><option value="table">Table</option><option value="seat">Seat</option><option value="queue">Queue</option><option value="dealer">Dealer</option><option value="restricted">Restricted</option></select></label>
                  <label>Color<input type="color" value={draft.color ?? COLORS[draft.zone_type]} onChange={(event) => setDraft({ ...draft, color: event.target.value })} /></label>
                </div>
                <div className="zone-field-row">
                  <label>Capacity<input type="number" min="1" value={draft.capacity} onChange={(event) => setDraft({ ...draft, capacity: Number(event.target.value) })} /></label>
                  <label>Dwell alert (sec)<input type="number" min="0" value={draft.dwell_alert_seconds} onChange={(event) => setDraft({ ...draft, dwell_alert_seconds: Number(event.target.value) })} /></label>
                </div>
                <label className="toggle compact"><input type="checkbox" checked={draft.enabled} onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })} /><span />Active in analytics</label>
                <div className="point-status"><span>{draft.polygon_normalized.length} points</span><span>{mode === 'drawing' ? 'Click video to continue drawing' : 'Drag a point to reshape'}</span></div>
                <div className="zone-form-actions">
                  <button onClick={() => setDraft({ ...draft, polygon_normalized: draft.polygon_normalized.slice(0, -1) })} disabled={!draft.polygon_normalized.length}>Undo point</button>
                  <button onClick={cancelDraft}>Cancel</button>
                  <button className="primary" onClick={() => void save()} disabled={busy || !dirty}>{busy ? 'Saving…' : 'Save zone'}</button>
                </div>
              </>
            )}
            {error && <p className="zone-error" role="alert">{error}</p>}
          </div>
        </div>
      </section>
    </>
  )
}

function readError(reason: unknown) {
  if (!(reason instanceof Error)) return 'Unable to save the zone.'
  try {
    const parsed = JSON.parse(reason.message) as { detail?: string | { message?: string } }
    return typeof parsed.detail === 'string' ? parsed.detail : parsed.detail?.message ?? reason.message
  } catch {
    return reason.message
  }
}

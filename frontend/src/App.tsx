import { useMemo, useState } from 'react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, streamUrl } from './api'
import type { EventItem } from './types'
import { useLiveData } from './useLiveData'
import './styles.css'

const CAMERA_ID = 'demo-table-01'

function formatEventName(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function fmtTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit', second: '2-digit' }).format(new Date(value))
}

function MetricCard({ label, value, detail, tone = 'plain' }: { label: string; value: string; detail: string; tone?: string }) {
  return (
    <article className={`metric-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  )
}

function EventFeed({ events, onFeedback }: { events: EventItem[]; onFeedback: (event: EventItem, status: 'acknowledged' | 'dismissed') => void }) {
  return (
    <section className="panel event-panel">
      <div className="panel-heading"><div><span className="eyebrow">ACTIVITY</span><h2>Recent events</h2></div><span className="count-badge">{events.length}</span></div>
      <div className="event-list">
        {events.length === 0 && <p className="empty">Events appear when occupancy changes.</p>}
        {events.slice(0, 12).map((event) => (
          <article className="event-row" key={event.event_id}>
            <span className={`event-dot ${event.severity}`} />
            <div className="event-copy">
              <strong>{formatEventName(event.event_type)}</strong>
              <span>{event.zone_id ?? 'Camera'} · {fmtTime(event.occurred_at)}</span>
              {event.track_id !== null && <small>Anonymous person #{event.track_id}</small>}
            </div>
            {event.feedback_status ? <span className="reviewed">{event.feedback_status}</span> : (
              <div className="event-actions">
                <button aria-label="Acknowledge event" onClick={() => onFeedback(event, 'acknowledged')}>✓</button>
                <button aria-label="Dismiss event" onClick={() => onFeedback(event, 'dismissed')}>×</button>
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}

export default function App() {
  const { live, connected, history, events, setArchivedEvents } = useLiveData()
  const [overlays, setOverlays] = useState(true)
  const [busy, setBusy] = useState(false)
  const [sourceMode, setSourceMode] = useState<'demo' | 'webcam'>('demo')
  const camera = live?.camera
  const table = live?.metrics.find((metric) => metric.zone_id === 'table-1')
  const seats = live?.metrics.filter((metric) => metric.zone_id.startsWith('seat-')) ?? []
  const occupiedSeats = seats.filter((seat) => seat.occupancy > 0).length
  const trend = useMemo(() => history.map((point) => ({ ...point, label: fmtTime(point.timestamp) })), [history])

  async function control(action: () => Promise<unknown>) {
    setBusy(true)
    try { await action() } finally { setBusy(false) }
  }

  async function feedback(event: EventItem, status: 'acknowledged' | 'dismissed') {
    const updated = await api.feedback(event.event_id, status)
    setArchivedEvents((current) => [updated, ...current.filter((item) => item.event_id !== updated.event_id)])
  }

  const status = camera?.status ?? 'starting'
  return (
    <main>
      <header className="topbar">
        <div className="brand"><span className="brand-mark">V</span><div><strong>VERATEX</strong><small>VIDEO INTELLIGENCE</small></div></div>
        <div className="header-context"><span>OPERATIONS / LIVE</span><strong>{camera?.name ?? 'Demo Table 1'}</strong></div>
        <div className={`connection ${connected ? 'online' : ''}`}><span />{connected ? 'Live updates' : 'Reconnecting'}</div>
      </header>

      <div className="dashboard-shell">
        <section className="intro">
          <div><span className="eyebrow">REAL-TIME FLOOR VIEW</span><h1>Table intelligence, at a glance.</h1><p>Anonymous occupancy and utilization signals from a continuous local feed.</p></div>
          <div className="source-health"><span className={`status-light ${status}`} /><div><small>SOURCE HEALTH</small><strong>{status.toUpperCase()}</strong></div><span>{camera?.processing_latency_ms ?? 0} ms</span></div>
        </section>

        <section className="metrics-grid">
          <MetricCard label="CURRENT OCCUPANCY" value={`${table?.occupancy ?? 0}`} detail={`of ${table?.capacity ?? 6} table capacity`} tone="mint" />
          <MetricCard label="OCCUPIED SEATS" value={`${occupiedSeats} / 6`} detail={`${6 - occupiedSeats} seats available`} tone="amber" />
          <MetricCard label="UTILIZATION" value={`${table?.utilization_pct ?? 0}%`} detail="current table load" />
          <MetricCard label="AVERAGE DWELL" value={`${Math.round(table?.average_dwell_seconds ?? 0)}s`} detail={`${table?.entries_total ?? 0} entries · ${table?.exits_total ?? 0} exits`} />
          <MetricCard label="PIPELINE LATENCY" value={`${camera?.processing_latency_ms ?? 0}ms`} detail={`${camera?.fps_inference ?? 0} inference FPS`} />
        </section>

        <section className="main-grid">
          <section className="panel video-panel">
            <div className="panel-heading"><div><span className="eyebrow">CAMERA 01</span><h2>Live annotated feed</h2></div><span className="privacy-badge">ANONYMOUS TRACKING</span></div>
            <div className="video-frame">
              <img src={streamUrl(CAMERA_ID)} alt="Live annotated demo table video" />
              <div className="live-chip"><span />LIVE</div>
              {status !== 'online' && <div className="video-state"><strong>{status === 'starting' ? 'Starting video pipeline…' : 'Source unavailable'}</strong><span>{camera?.last_error ?? 'Waiting for the next frame'}</span></div>}
            </div>
            <div className="seat-strip">
              {Array.from({ length: 6 }, (_, index) => seats.find((seat) => seat.zone_id === `seat-${index + 1}`)).map((seat, index) => (
                <div className={seat?.occupancy ? 'seat occupied' : 'seat'} key={index}><span>{index + 1}</span><small>{seat?.occupancy ? 'Occupied' : 'Available'}</small></div>
              ))}
            </div>
          </section>

          <EventFeed events={events} onFeedback={feedback} />

          <section className="panel trend-panel">
            <div className="panel-heading"><div><span className="eyebrow">LAST 30 MINUTES</span><h2>Table utilization</h2></div><strong className="trend-value">{table?.utilization_pct ?? 0}%</strong></div>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trend} margin={{ top: 12, right: 6, left: -22, bottom: 0 }}>
                  <defs><linearGradient id="utilization" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#56d7b0" stopOpacity={0.38} /><stop offset="100%" stopColor="#56d7b0" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid stroke="#27333d" vertical={false} />
                  <XAxis dataKey="label" stroke="#72808c" tickLine={false} axisLine={false} minTickGap={35} />
                  <YAxis domain={[0, 100]} stroke="#72808c" tickLine={false} axisLine={false} unit="%" />
                  <Tooltip contentStyle={{ background: '#111a22', border: '1px solid #31404c', borderRadius: 8 }} />
                  <Area type="monotone" dataKey="utilization_pct" stroke="#56d7b0" strokeWidth={2} fill="url(#utilization)" />
                </AreaChart>
              </ResponsiveContainer>
              {trend.length === 0 && <span className="chart-empty">Trend points accumulate while the demo runs.</span>}
            </div>
          </section>

          <section className="panel controls-panel">
            <div className="panel-heading"><div><span className="eyebrow">LOCAL DEMO</span><h2>Source controls</h2></div></div>
            <label>Camera<select aria-label="Camera"><option>Demo Table 1 — Camera 01</option></select></label>
            <label>Video source<select value={sourceMode} onChange={(event) => setSourceMode(event.target.value as 'demo' | 'webcam')}><option value="demo">Generated MP4 loop</option><option value="webcam">Webcam 0 + YOLO</option></select></label>
            <div className="control-buttons">
              <button className="primary" disabled={busy} onClick={() => control(() => sourceMode === 'demo' ? api.start(CAMERA_ID, 'file_loop', 'data/demo.mp4', 'synthetic') : api.start(CAMERA_ID, 'webcam', 0, 'yolo'))}>Start source</button>
              <button disabled={busy} onClick={() => control(() => api.stop(CAMERA_ID))}>Stop</button>
              <button disabled={busy} onClick={() => control(() => api.reset(CAMERA_ID))}>Reset metrics</button>
            </div>
            <label className="toggle"><input type="checkbox" checked={overlays} onChange={(event) => { const enabled = event.target.checked; setOverlays(enabled); void api.overlays(CAMERA_ID, enabled) }} /><span />Zone overlays</label>
            <div className="source-detail"><span>Input FPS <strong>{camera?.fps_input.toFixed(1) ?? '0.0'}</strong></span><span>Dropped frames <strong>{camera?.dropped_frames ?? 0}</strong></span></div>
          </section>
        </section>
      </div>
      <footer><span>Anonymous operational analytics only</span><span>No facial recognition · No video recording · Human review required</span></footer>
    </main>
  )
}

import { useMemo, useState } from 'react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, streamUrl } from './api'
import { eventDescription, formatEventName } from './eventDescription'
import type { EventItem, ZoneConfig } from './types'
import { useLiveData } from './useLiveData'
import { ZoneEditor } from './ZoneEditor'
import './styles.css'

const CAMERA_ID = 'demo-table-01'

function fmtTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit', second: '2-digit' }).format(new Date(value))
}

function MetricCard({ label, value, detail, tone = 'plain' }: { label: string; value: string; detail: string; tone?: string }) {
  return <article className={`metric-card ${tone}`}><span className="metric-label">{label}</span><strong className="metric-value">{value}</strong><small>{detail}</small></article>
}

function EventFeed({ events, zones }: { events: EventItem[]; zones: ZoneConfig[] }) {
  return (
    <section className="panel event-panel">
      <div className="panel-heading"><div><span className="eyebrow">ACTIVITY</span><h2>Recent events</h2></div><span className="count-badge">{events.length}</span></div>
      <div className="event-list">
        {events.length === 0 && <p className="event-empty">Events appear when people enter or exit one of your active zones.</p>}
        {events.slice(0, 12).map((event) => {
          const zone = zones.find((item) => item.zone_id === event.zone_id)
          const zoneType = String(event.attributes.zone_type ?? zone?.zone_type ?? 'camera')
          return (
            <article className="event-row" key={event.event_id}>
              <span className={`event-dot ${event.severity}`} />
              <div className="event-copy">
                <strong>{eventDescription(event, zones)}</strong>
                <span>{zone?.name ?? event.attributes.zone_name ?? event.zone_id ?? 'Camera'} · {formatEventName(zoneType)} · {fmtTime(event.occurred_at)}</span>
                <small>Occupancy {event.attributes.occupancy ?? '—'} / {event.attributes.capacity ?? zone?.capacity ?? '—'}</small>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}

export default function App() {
  const { live, connected, history, events, zones, zoneRevision, applyZoneCollection } = useLiveData()
  const [overlays, setOverlays] = useState(true)
  const [zoneEditorOpen, setZoneEditorOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [sourceMode, setSourceMode] = useState<'demo' | 'webcam'>('demo')
  const [imageElement, setImageElement] = useState<HTMLImageElement | null>(null)
  const [videoFrameElement, setVideoFrameElement] = useState<HTMLDivElement | null>(null)
  const camera = live?.camera
  const activeZones = zones.filter((zone) => zone.enabled)
  const primaryZone = activeZones.find((zone) => zone.zone_type === 'table') ?? activeZones[0]
  const primaryMetric = live?.metrics.find((metric) => metric.zone_id === primaryZone?.zone_id)
  const seatZones = activeZones.filter((zone) => zone.zone_type === 'seat')
  const seatMetrics = seatZones.map((zone) => ({ zone, metric: live?.metrics.find((item) => item.zone_id === zone.zone_id) }))
  const occupiedSeats = seatMetrics.filter(({ metric }) => (metric?.occupancy ?? 0) > 0).length
  const trend = useMemo(() => history.map((point) => ({ ...point, label: fmtTime(point.timestamp) })), [history])

  async function control(action: () => Promise<unknown>) {
    setBusy(true)
    try { await action() } finally { setBusy(false) }
  }

  function toggleZoneEditor(next: boolean) {
    setZoneEditorOpen(next)
    void api.overlays(CAMERA_ID, next ? false : overlays)
  }

  const status = camera?.status ?? 'starting'
  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#overview" aria-label="Veratex operations home"><span className="brand-mark">V</span><div><strong>veratex</strong><small>VIDEO INTELLIGENCE</small></div></a>
        <nav className="dashboard-nav" aria-label="Dashboard navigation"><a href="#overview">Overview</a><a href="#live-feed">Live feed</a><a href="#activity">Activity</a><a href="#controls">Controls</a></nav>
        <div className={`connection ${connected ? 'online' : ''}`}><span />{connected ? 'Live updates' : 'Reconnecting'}</div>
      </header>

      <div className="dashboard-shell" id="overview">
        <section className="intro">
          <div className="intro-copy"><span className="eyebrow">REAL-TIME FLOOR INTELLIGENCE</span><h1>Live intelligence.<br /><em>By design.</em></h1><p>Turn a continuous camera feed into clear occupancy, utilization, and dwell insights—without identifying a single person.</p><div className="hero-tags"><span>Anonymous tracking</span><span>Configurable zones</span><span>Live operational signals</span></div></div>
          <div className="source-health"><span className={`status-light ${status}`} /><div><small>SOURCE HEALTH</small><strong>{status.toUpperCase()}</strong></div><span className="health-latency">{camera?.processing_latency_ms ?? 0} ms</span></div>
        </section>

        <section className="metrics-grid">
          <MetricCard label="CURRENT OCCUPANCY" value={`${primaryMetric?.occupancy ?? 0}`} detail={primaryZone ? `${primaryZone.name} · capacity ${primaryMetric?.capacity ?? primaryZone.capacity}` : 'Draw a zone to begin'} tone="mint" />
          <MetricCard label="OCCUPIED SEATS" value={`${occupiedSeats} / ${seatZones.length}`} detail={`${Math.max(0, seatZones.length - occupiedSeats)} configured seats available`} tone="amber" />
          <MetricCard label="UTILIZATION" value={`${primaryMetric?.utilization_pct ?? 0}%`} detail={primaryZone ? `${primaryZone.name} current load` : 'No active zone'} />
          <MetricCard label="AVERAGE DWELL" value={`${Math.round(primaryMetric?.average_dwell_seconds ?? 0)}s`} detail={`${primaryMetric?.entries_total ?? 0} entries · ${primaryMetric?.exits_total ?? 0} exits`} />
          <MetricCard label="PIPELINE LATENCY" value={`${camera?.processing_latency_ms ?? 0}ms`} detail={`${camera?.fps_inference ?? 0} inference FPS`} />
        </section>

        <section className="main-grid">
          <section className="panel video-panel" id="live-feed">
            <div className="panel-heading"><div><span className="eyebrow">CAMERA 01</span><h2>Live annotated feed</h2></div><div className="video-heading-actions"><span className="privacy-badge">ANONYMOUS TRACKING</span><button className="secondary-button" disabled={zoneEditorOpen} onClick={() => toggleZoneEditor(true)}>{zoneEditorOpen ? 'Editor open' : 'Edit zones'}</button></div></div>
            <div className="video-frame" ref={setVideoFrameElement}>
              <img ref={setImageElement} src={streamUrl(CAMERA_ID)} alt="Live annotated demo table video" />
              <div className="live-chip"><span />LIVE</div>
              {zoneEditorOpen && <div className="editing-chip">ZONE EDITING</div>}
              {status !== 'online' && <div className="video-state"><strong>{status === 'starting' ? 'Starting video pipeline…' : 'Source unavailable'}</strong><span>{camera?.last_error ?? 'Waiting for the next frame'}</span></div>}
            </div>
            {seatMetrics.length > 0 && <div className="seat-strip" style={{ gridTemplateColumns: `repeat(${Math.min(seatMetrics.length, 6)}, 1fr)` }}>{seatMetrics.map(({ zone, metric }) => <div className={metric?.occupancy ? 'seat occupied' : 'seat'} key={zone.zone_id}><span>{zone.name.replace(/^Seat\s*/i, '') || '•'}</span><small>{metric?.occupancy ? 'Occupied' : 'Available'}</small></div>)}</div>}
            <ZoneEditor cameraId={CAMERA_ID} image={imageElement} overlayHost={videoFrameElement} zones={zones} revision={zoneRevision} open={zoneEditorOpen} onClose={() => toggleZoneEditor(false)} onChange={applyZoneCollection} />
          </section>

          <div id="activity"><EventFeed events={events} zones={zones} /></div>

          <section className="panel trend-panel">
            <div className="panel-heading"><div><span className="eyebrow">LAST 30 MINUTES</span><h2>{primaryZone?.name ?? 'Zone'} utilization</h2></div><strong className="trend-value">{primaryMetric?.utilization_pct ?? 0}%</strong></div>
            <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={trend} margin={{ top: 12, right: 6, left: -22, bottom: 0 }}><defs><linearGradient id="utilization" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#12aaa5" stopOpacity={0.3} /><stop offset="100%" stopColor="#12aaa5" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="#e4ebf2" vertical={false} /><XAxis dataKey="label" stroke="#78879a" tickLine={false} axisLine={false} minTickGap={35} /><YAxis domain={[0, 100]} stroke="#78879a" tickLine={false} axisLine={false} unit="%" /><Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #dbe4ed', borderRadius: 10, color: '#0b1730', boxShadow: '0 12px 30px rgba(24,54,91,.1)' }} /><Area type="monotone" dataKey="utilization_pct" stroke="#12aaa5" strokeWidth={2} fill="url(#utilization)" /></AreaChart></ResponsiveContainer>{trend.length === 0 && <span className="chart-empty">Trend points accumulate while the demo runs.</span>}</div>
          </section>

          <section className="panel controls-panel" id="controls">
            <div className="panel-heading"><div><span className="eyebrow">LOCAL DEMO</span><h2>Source controls</h2></div></div>
            <div className="control-body">
              <label>Camera<select aria-label="Camera"><option>Demo Table 1 — Camera 01</option></select></label>
              <label>Video source<select value={sourceMode} onChange={(event) => setSourceMode(event.target.value as 'demo' | 'webcam')}><option value="demo">Generated MP4 loop</option><option value="webcam">Webcam 0 + YOLO</option></select></label>
              <div className="control-buttons"><button className="primary-button" disabled={busy} onClick={() => control(() => sourceMode === 'demo' ? api.start(CAMERA_ID, 'file_loop', 'data/demo.mp4', 'synthetic') : api.start(CAMERA_ID, 'webcam', 0, 'yolo'))}>Start source</button><button className="ghost-button" disabled={busy} onClick={() => control(() => api.stop(CAMERA_ID))}>Stop</button><button className="ghost-button" disabled={busy} onClick={() => control(() => api.reset(CAMERA_ID))}>Reset metrics</button></div>
              <label className="toggle-row"><span>Zone overlays</span><input type="checkbox" checked={overlays} disabled={zoneEditorOpen} onChange={(event) => { const enabled = event.target.checked; setOverlays(enabled); void api.overlays(CAMERA_ID, enabled) }} /></label>
              <div className="source-detail"><span>Active zones <strong>{activeZones.length}</strong></span><span>Revision <strong>{zoneRevision}</strong></span><span>Dropped <strong>{camera?.dropped_frames ?? 0}</strong></span></div>
            </div>
          </section>
        </section>
      </div>
      <footer className="footer"><span>Anonymous operational analytics only</span><span>No facial recognition · No video recording · Human review required</span></footer>
    </main>
  )
}

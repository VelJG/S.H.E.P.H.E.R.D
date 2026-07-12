import { useEffect, useMemo, useRef, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { Frame, Incident, LiveSource, Zone, ZoneMetric, ZoneStatus } from '../types';
import { DEFAULT_FRAME_H, DEFAULT_FRAME_W } from '../types';
import CameraStage from './CameraStage';
import { useLiveData } from '../lib/useLiveData';

const STATUS_COLOR: Record<ZoneStatus, string> = {
  normal: '#46c06a',
  warning: '#d6a743',
  congested: '#ef5b47',
};

function fmtWait(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function timeAgo(ts: number): string {
  const d = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  return d >= 60 ? `${Math.floor(d / 60)}m` : `${d}s`;
}

const OTHER_CAMS = [
  { id: 'CAM-01', name: 'Entrance' },
  { id: 'CAM-02', name: 'Hall' },
  { id: 'CAM-04', name: 'Exit' },
  { id: 'CAM-05', name: 'Lobby' },
];

const env = (import.meta as any).env ?? {};
const liveFrameWidth = numberEnv('VITE_LIVE_FRAME_WIDTH', DEFAULT_FRAME_W);
const liveFrameHeight = numberEnv('VITE_LIVE_FRAME_HEIGHT', DEFAULT_FRAME_H);

type Props = {
  zones: Zone[];
  frame: Frame;
  clock: string;
  liveSource: LiveSource;
  setLiveSource: Dispatch<SetStateAction<LiveSource>>;
  onEditZonesFromLive: () => Promise<void>;
};

function numberEnv(name: string, fallback: number): number {
  const value = Number(env[name]);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function cacheBustedUrl(value: string, key: string, tick: number): string {
  try {
    const url = new URL(value, window.location.href);
    url.searchParams.set(key, String(tick));
    return url.toString();
  } catch {
    return value;
  }
}

export default function LiveMonitor({ zones, frame, clock, liveSource, setLiveSource, onEditZonesFromLive }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const heatCanvasRef = useRef<HTMLCanvasElement>(null);
  const [snapshotTick, setSnapshotTick] = useState(() => Date.now());
  const [capturingLiveFrame, setCapturingLiveFrame] = useState(false);

  const trimmedStreamUrl = liveSource.streamUrl.trim();
  const trimmedSnapshotUrl = liveSource.snapshotUrl.trim();
  const hasStream = Boolean(trimmedStreamUrl);
  const hasSnapshot = Boolean(trimmedSnapshotUrl);
  const hasRelay = hasStream || hasSnapshot;
  const snapshotOnly = hasSnapshot && !hasStream;
  const liveFrame: Frame = hasRelay
    ? { width: liveFrameWidth, height: liveFrameHeight, url: hasStream ? trimmedStreamUrl : trimmedSnapshotUrl, kind: 'image' }
    : frame;

  const fullFrameZone = useMemo<Zone>(() => ({
    id: 'live-full-frame',
    name: 'Live Camera Full Frame',
    color: '#4c9aff',
    points: [
      { x: 0, y: 0 },
      { x: liveFrame.width, y: 0 },
      { x: liveFrame.width, y: liveFrame.height },
      { x: 0, y: liveFrame.height },
    ],
    warnAt: 4,
    congestAt: 7,
    avgServiceSec: 20,
  }), [liveFrame.height, liveFrame.width]);

  const activeZones = zones.length ? zones : hasRelay ? [fullFrameZone] : zones;
  const live = useLiveData(activeZones, liveFrame, videoRef, heatCanvasRef, {
    snapshotUrl: hasSnapshot ? trimmedSnapshotUrl : '',
  });
  const displayFrame: Frame = snapshotOnly
    ? { ...liveFrame, url: cacheBustedUrl(trimmedSnapshotUrl, '_viewTs', snapshotTick) }
    : liveFrame;

  useEffect(() => {
    if (!snapshotOnly || !live.running) return;
    const delay = Math.max(250, Math.min(1000, live.intervalMs));
    const timer = window.setTimeout(() => setSnapshotTick(Date.now()), delay);
    return () => window.clearTimeout(timer);
  }, [live.intervalMs, live.running, snapshotOnly, snapshotTick]);

  const updateRelaySource = (patch: Partial<LiveSource>) => {
    setLiveSource((previous) => ({ ...previous, ...patch }));
  };

  const editZonesFromLive = async () => {
    if (!trimmedSnapshotUrl || capturingLiveFrame) return;
    setCapturingLiveFrame(true);
    try {
      await onEditZonesFromLive();
    } finally {
      setCapturingLiveFrame(false);
    }
  };

  const metricList: ZoneMetric[] = activeZones.map(
    (z) => live.metrics[z.id] ?? { zoneId: z.id, personCount: 0, waitSec: 0, status: 'normal' },
  );
  const hottest = metricList.reduce(
    (a, b) => (numHeat(b) > numHeat(a) ? b : a),
    metricList[0] ?? { zoneId: '', personCount: 0, waitSec: 0, status: 'normal' as ZoneStatus },
  );
  const openIncidents = live.incidents.filter((i) => i.status !== 'resolved');
  const inZones = metricList.reduce((a, m) => a + m.personCount, 0);
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="spotlight">
      <div className="spotlight__body">
        <div className="center">
          <div className="tiles">
            <Tile label="People in zones" value={String(inZones)} delta={`${activeZones.length} zones`} />
            <Tile label="Active IDs" value={String(live.tracks.length)} delta={live.processing ? 'processing' : `${live.latencyMs}ms`} color="#f7b955" />
            <Tile
              label="Hottest zone"
              value={activeZones.find((z) => z.id === hottest.zoneId)?.name ?? 'None'}
              delta={`heat ${numHeat(hottest).toFixed(2)}`}
              color={STATUS_COLOR[hottest.status]}
            />
            <Tile
              label="Open incidents"
              value={String(openIncidents.length)}
              delta="temporal"
              color={openIncidents.length ? '#ef5b47' : '#46c06a'}
            />
          </div>

          <div className="live-source-panel">
            <div className="live-source-panel__head">
              <span className="rail__label">LIVE IP CAMERA RELAY</span>
              <span className={`source-state ${hasRelay ? 'source-state--on' : ''}`}>
                {hasSnapshot ? (hasStream ? 'stream + AI ready' : 'snapshot live ready') : hasStream ? 'stream only' : 'waiting for relay URL'}
              </span>
            </div>
            <div className="live-source-grid">
              <label>
                Stream URL (optional)
                <input
                  className="input"
                  placeholder="https://xxxx.trycloudflare.com/stream.mjpg"
                  value={liveSource.streamUrl}
                  onChange={(event) => updateRelaySource({ streamUrl: event.target.value })}
                />
              </label>
              <label>
                Snapshot URL (fastest)
                <input
                  className="input"
                  placeholder="https://xxxx.trycloudflare.com/snapshot.jpg"
                  value={liveSource.snapshotUrl}
                  onChange={(event) => updateRelaySource({ snapshotUrl: event.target.value })}
                />
              </label>
            </div>
            <p className="savehint">
              Fastest mode: leave Stream URL blank and paste Snapshot URL only. The visual feed will poll snapshots while AI uses the same source.
            </p>
          </div>

          <div className="feed">
            {displayFrame.kind === 'video' && displayFrame.url && (
              <video ref={videoRef} className="feedvideo" src={displayFrame.url} autoPlay loop muted playsInline />
            )}
            {displayFrame.kind === 'image' && displayFrame.url && (
              <img className="feedvideo" src={displayFrame.url} alt={hasRelay ? 'Live IP camera feed' : 'Uploaded camera frame'} />
            )}
            <canvas ref={heatCanvasRef} className="heatmap-layer" aria-hidden="true" />
            <CameraStage zones={activeZones} frame={displayFrame} metrics={live.metrics} tracks={live.tracks} mode="live" />
            <div className="ov ov-live">
              <span className="ov-live__dot rec" style={{ background: live.connected ? '#ef5b47' : '#565c65' }} />
              <span className="ov-live__txt">{live.connected ? 'LIVE' : 'OFFLINE'}</span>
            </div>
            <div className="ov ov-res">{displayFrame.width} x {displayFrame.height} - {live.latencyMs || 0}ms</div>
            <div className="ov ov-cam">{hasRelay ? (snapshotOnly ? 'IP CAM SNAPSHOT' : 'IP CAM RELAY') : 'CAM-03 - Main'}</div>
            <div className="ov ov-time">{today} {clock}</div>
          </div>

          <div className="livebar">
            <span className="livebar__pill" style={{ background: live.connected ? '#ef5b47' : '#565c65' }}>
              <span className="livebar__dot blink" />{live.connected ? 'VISION LIVE' : 'NO PIPELINE'}
            </span>
            <button className="btn pausebtn" disabled={!liveFrame.url} onClick={() => live.setRunning(!live.running)}>{live.running ? 'Pause' : 'Resume / Start'}</button>
            <button className="btn btn--primary" disabled={!trimmedSnapshotUrl || capturingLiveFrame} onClick={() => void editZonesFromLive()}>
              {capturingLiveFrame ? 'Loading live frame...' : 'Edit zones on live frame'}
            </button>
            <button className="btn" onClick={() => void live.reset()}>Reset IDs + heat</button>
            <label className="interval-control">
              Interval ms
              <input type="number" min={1} value={live.intervalMs} onChange={(event) => live.setIntervalMs(Number(event.target.value))} />
            </label>
            {live.processing && <span className="pipeline-note">YOLO to tracking to heatmap</span>}
            {live.error && <span className="pipeline-error" title={live.error}>{live.error}</span>}
          </div>

          <div className="camstrip">
            {OTHER_CAMS.map((c) => (
              <div key={c.id} className="camthumb">
                <div className="camthumb__grid" />
                <div className="camthumb__label">{c.id} {c.name}</div>
              </div>
            ))}
          </div>
        </div>

        <aside className="rail">
          <span className="rail__label">ZONES</span>
          <div className="zoneslist">
            {zones.length === 0 && hasRelay && <p className="muted small">No zones saved. Using full-frame live camera zone for demo tracking.</p>}
            {zones.length === 0 && !hasRelay && <p className="muted small">No zones defined. Draw them in the Zone Editor.</p>}
            {activeZones.map((z) => {
              const m = live.metrics[z.id];
              const st = m?.status ?? 'normal';
              return (
                <div key={z.id} className="zonerow">
                  <span className="zonebar" style={{ background: STATUS_COLOR[st] }} />
                  <div className="zonerow__body">
                    <div className="zonerow__name">{z.name}</div>
                    <div className="zonerow__wait">wait ~{fmtWait(m?.waitSec ?? 0)} - heat {(m?.heatMean ?? 0).toFixed(2)}</div>
                  </div>
                  <span className="zonerow__count" style={{ color: STATUS_COLOR[st] }}>{m?.personCount ?? 0}</span>
                </div>
              );
            })}
          </div>

          <ActivityChart history={live.history} />

          <div className="rail__head">
            <span className="rail__label">EVENTS</span>
            {openIncidents.length > 0 && <span className="rail__new">{openIncidents.length} NEW</span>}
          </div>
          {live.incidents.length === 0 && (
            <p className="muted small">No incidents. They appear when the processor reports congestion.</p>
          )}
          {live.incidents.map((i) => (
            <EventCard key={i.id} inc={i} onAck={live.ackIncident} onResolve={live.resolveIncident} />
          ))}
        </aside>
      </div>
    </div>
  );
}

function numHeat(metric: ZoneMetric): number {
  return metric.heatMean ?? 0;
}

function Tile({ label, value, delta, color }: { label: string; value: string; delta?: string; color?: string }) {
  return (
    <div className="tile">
      <div className="tile__label">{label}</div>
      <div className="tile__row">
        <span className="tile__value" style={color ? { color } : undefined}>{value}</span>
        {delta && <span className="tile__delta">{delta}</span>}
      </div>
    </div>
  );
}

const BADGE: Record<Incident['status'], { text: string; color: string }> = {
  open: { text: 'OPEN', color: '#ef5b47' },
  acknowledged: { text: 'ACK', color: '#d6a743' },
  resolved: { text: 'RESOLVED', color: '#46c06a' },
};

function EventCard({
  inc,
  onAck,
  onResolve,
}: {
  inc: Incident;
  onAck: (id: string) => void;
  onResolve: (id: string) => void;
}) {
  const b = BADGE[inc.status];
  return (
    <div className={`event event--${inc.status}`}>
      <div className="event__thumb" />
      <div className="event__body">
        <div className="event__top">
          <span className="event__badge" style={{ background: b.color }}>{b.text}</span>
          <span className="event__id">{inc.id} - {timeAgo(inc.createdAt)}</span>
        </div>
        <div className="event__title">{inc.zoneName} congested</div>
        <div className="event__desc">{inc.personCount} people over threshold</div>
        {inc.status !== 'resolved' && (
          <div className="event__actions">
            {inc.status === 'open' && <button className="btn" onClick={() => onAck(inc.id)}>Acknowledge</button>}
            <button className="btn btn--primary" onClick={() => onResolve(inc.id)}>Resolve</button>
          </div>
        )}
      </div>
    </div>
  );
}

function ActivityChart({ history }: { history: { total: number }[] }) {
  const totals = history.map((h) => h.total);
  const max = Math.max(6, ...totals);
  return (
    <div className="chart">
      <div className="chart__head">
        <span className="chart__title">Total people - live</span>
        <span className="chart__max">max {max}</span>
      </div>
      <div className="chart__bars">
        {totals.map((v, i) => {
          const ratio = v / max;
          const hot = ratio >= 0.85;
          return (
            <div
              key={i}
              className="bar"
              style={{ height: `${Math.max(4, ratio * 100)}%`, background: hot ? '#ef5b47' : '#4c9aff', opacity: 0.5 + 0.45 * ratio }}
            />
          );
        })}
      </div>
    </div>
  );
}

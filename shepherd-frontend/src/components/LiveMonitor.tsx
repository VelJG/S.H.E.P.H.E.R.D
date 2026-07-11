import type { Frame, Incident, Zone, ZoneMetric, ZoneStatus } from '../types';
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

type Props = { zones: Zone[]; frame: Frame; clock: string };

export default function LiveMonitor({ zones, frame, clock }: Props) {
  const live = useLiveData(zones);
  const metricList: ZoneMetric[] = zones.map(
    (z) => live.metrics[z.id] ?? { zoneId: z.id, personCount: 0, waitSec: 0, status: 'normal' },
  );
  const busiest = metricList.reduce(
    (a, b) => (b.personCount > a.personCount ? b : a),
    metricList[0] ?? { zoneId: '', personCount: 0, waitSec: 0, status: 'normal' as ZoneStatus },
  );
  const openIncidents = live.incidents.filter((i) => i.status !== 'resolved');
  const longestWait = Math.max(0, ...metricList.map((m) => m.waitSec));
  const inZones = metricList.reduce((a, m) => a + m.personCount, 0);
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="spotlight">
      <div className="spotlight__body">
        <div className="center">
          <div className="tiles">
            <Tile label="People in zones" value={String(inZones)} delta={`${zones.length} zones`} />
            <Tile
              label="Busiest zone"
              value={zones.find((z) => z.id === busiest.zoneId)?.name ?? 'None'}
              delta={`${busiest.personCount}`}
              color={STATUS_COLOR[busiest.status]}
            />
            <Tile
              label="Open incidents"
              value={String(openIncidents.length)}
              delta="pending"
              color={openIncidents.length ? '#ef5b47' : '#46c06a'}
            />
            <Tile label="Longest wait" value={fmtWait(longestWait)} color="#d6a743" />
          </div>

          <div className="feed">
            {frame.kind === 'video' && frame.url && (
              <video className="feedvideo" src={frame.url} autoPlay loop muted playsInline />
            )}
            <CameraStage zones={zones} frame={frame} metrics={live.metrics} mode="live" />
            <div className="ov ov-live">
              <span className="ov-live__dot rec" style={{ background: live.connected ? '#ef5b47' : '#565c65' }} />
              <span className="ov-live__txt">{live.connected ? 'LIVE' : 'OFFLINE'}</span>
            </div>
            <div className="ov ov-res">{frame.width} x {frame.height} - 15fps</div>
            <div className="ov ov-cam">CAM-03 - Main</div>
            <div className="ov ov-time">{today} {clock}</div>
          </div>

          <div className="livebar">
            <span className="livebar__pill" style={{ background: live.connected ? '#ef5b47' : '#565c65' }}>
              <span className="livebar__dot blink" />{live.connected ? 'LIVE' : 'NO API'}
            </span>
            <button className="btn pausebtn" onClick={() => live.setRunning(!live.running)}>
              {live.running ? 'Pause' : 'Resume'}
            </button>
            {!live.connected && (
              <span className="muted small" style={{ marginLeft: 10 }}>
                Waiting for backend — set VITE_API_URL and run the processor.
              </span>
            )}
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
            {zones.length === 0 && <p className="muted small">No zones defined. Draw them in the Zone Editor.</p>}
            {zones.map((z) => {
              const m = live.metrics[z.id];
              const st = m?.status ?? 'normal';
              return (
                <div key={z.id} className="zonerow">
                  <span className="zonebar" style={{ background: STATUS_COLOR[st] }} />
                  <div className="zonerow__body">
                    <div className="zonerow__name">{z.name}</div>
                    <div className="zonerow__wait">wait ~{fmtWait(m?.waitSec ?? 0)}</div>
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

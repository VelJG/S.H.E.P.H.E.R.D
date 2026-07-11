import type { Frame, Incident, Zone, ZoneMetric, ZoneStatus } from '../types';
import CameraStage from './CameraStage';
import { useSimulation } from '../lib/useSimulation';

const STATUS_COLOR: Record<ZoneStatus, string> = {
  normal: '#22c55e',
  warning: '#ff9900',
  congested: '#ff4d4f',
};

function fmtWait(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

type Props = { zones: Zone[]; frame: Frame };

export default function LiveMonitor({ zones, frame }: Props) {
  const sim = useSimulation(zones, frame.width, frame.height);
  const metricList: ZoneMetric[] = zones.map(
    (z) => sim.metrics[z.id] ?? { zoneId: z.id, personCount: 0, waitSec: 0, status: 'normal' },
  );
  const busiest = metricList.reduce(
    (a, b) => (b.personCount > a.personCount ? b : a),
    metricList[0] ?? { zoneId: '', personCount: 0, waitSec: 0, status: 'normal' as ZoneStatus },
  );
  const openIncidents = sim.incidents.filter((i) => i.status !== 'resolved');
  const longestWait = Math.max(0, ...metricList.map((m) => m.waitSec));

  return (
    <div className="live">
      <div className="live__main">
        <div className="tiles">
          <Tile label="Người trên camera" value={String(sim.tracks.length)} accent="#00a9e0" />
          <Tile label="Quầy đông nhất" value={zones.find((z) => z.id === busiest.zoneId)?.name ?? '—'}
            sub={`${busiest.personCount} người`} accent={STATUS_COLOR[busiest.status]} />
          <Tile label="Sự cố đang mở" value={String(openIncidents.length)} accent={openIncidents.length ? '#ff4d4f' : '#22c55e'} />
          <Tile label="Chờ lâu nhất" value={fmtWait(longestWait)} accent="#ff9900" />
        </div>

        <div className="stagewrap">
          <span className="livebadge">● LIVE</span>
          <button className="btn btn--ghost pausebtn" onClick={() => sim.setRunning(!sim.running)}>
            {sim.running ? '⏸ Tạm dừng' : '▶ Chạy'}
          </button>
          <CameraStage zones={zones} frame={frame} tracks={sim.tracks} metrics={sim.metrics} mode="live" />
        </div>

        <ActivityChart history={sim.history} />
      </div>

      <aside className="live__side">
        <h3>Zones</h3>
        <div className="zstatus">
          {zones.map((z) => {
            const m = sim.metrics[z.id];
            const st = m?.status ?? 'normal';
            return (
              <div key={z.id} className="zstatus__row">
                <span className="statusbar" style={{ background: STATUS_COLOR[st] }} />
                <div className="zstatus__body">
                  <div className="zstatus__name">{z.name}</div>
                  <div className="muted small">chờ ~{fmtWait(m?.waitSec ?? 0)}</div>
                </div>
                <div className="zstatus__count" style={{ color: STATUS_COLOR[st] }}>
                  {m?.personCount ?? 0}
                </div>
              </div>
            );
          })}
        </div>

        <h3>Incidents ({openIncidents.length})</h3>
        <div className="incidents">
          {sim.incidents.length === 0 && <p className="muted small">Chưa có sự cố. Chờ quầy nào đó tắc nghẽn…</p>}
          {sim.incidents.map((i) => (
            <IncidentRow key={i.id} inc={i} onAck={sim.ackIncident} onResolve={sim.resolveIncident} />
          ))}
        </div>
      </aside>
    </div>
  );
}

function Tile({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent: string }) {
  return (
    <div className="tile">
      <div className="tile__label">{label}</div>
      <div className="tile__value" style={{ color: accent }}>{value}</div>
      {sub && <div className="tile__sub">{sub}</div>}
    </div>
  );
}

function IncidentRow({ inc, onAck, onResolve }: {
  inc: Incident; onAck: (id: string) => void; onResolve: (id: string) => void;
}) {
  const badge = inc.status === 'open' ? '#ff4d4f' : inc.status === 'acknowledged' ? '#ff9900' : '#22c55e';
  return (
    <div className="incrow">
      <div className="incrow__top">
        <span className="incbadge" style={{ background: badge }}>{inc.status}</span>
        <span className="incrow__id">{inc.id}</span>
      </div>
      <div className="incrow__msg">{inc.zoneName} tắc nghẽn — {inc.personCount} người</div>
      <div className="incrow__actions">
        {inc.status === 'open' && <button className="btn btn--sm" onClick={() => onAck(inc.id)}>Acknowledge</button>}
        {inc.status !== 'resolved' && <button className="btn btn--sm btn--primary" onClick={() => onResolve(inc.id)}>Resolve</button>}
      </div>
    </div>
  );
}

function ActivityChart({ history }: { history: { counts: Record<string, number> }[] }) {
  const W = 1000;
  const H = 140;
  const pad = 24;
  const totals = history.map((h) => Object.values(h.counts).reduce((a, b) => a + b, 0));
  const max = Math.max(6, ...totals);
  const bw = (W - pad * 2) / Math.max(1, history.length);
  return (
    <div className="chart">
      <div className="chart__title">Tổng người trong các zone theo thời gian</div>
      <svg viewBox={`0 0 ${W} ${H}`} className="chart__svg" preserveAspectRatio="none">
        {totals.map((v, i) => {
          const h = (v / max) * (H - pad * 2);
          return (
            <rect key={i} x={pad + i * bw + 2} y={H - pad - h} width={Math.max(3, bw - 4)} height={h}
              rx={2} fill="#00a9e0" opacity={0.55 + 0.45 * (v / max)} />
          );
        })}
        <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} stroke="#2b3a4d" strokeWidth={1} />
      </svg>
    </div>
  );
}

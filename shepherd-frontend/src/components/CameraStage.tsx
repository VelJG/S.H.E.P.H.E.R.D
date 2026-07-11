import type React from 'react';
import type { Frame, Point, Track, Zone, ZoneMetric, ZoneStatus } from '../types';
import { polygonPath } from '../lib/geometry';

const STATUS_COLOR: Record<ZoneStatus, string> = {
  normal: '#46c06a',
  warning: '#d6a743',
  congested: '#ef5b47',
};
const DETECT = '#4c9aff';

type Props = {
  zones: Zone[];
  frame: Frame;
  tracks?: Track[];
  metrics?: Record<string, ZoneMetric>;
  mode: 'live' | 'editor';
  draft?: Point[];
  selectedZoneId?: string | null;
  onStageClick?: (p: Point) => void;
};

/** Stable per-track detection confidence, just for the CCTV look. */
function conf(id: number): string {
  return (0.86 + ((id * 37) % 12) / 100).toFixed(2);
}

function bbox(poly: Point[]) {
  const xs = poly.map((p) => p.x);
  const ys = poly.map((p) => p.y);
  return { minX: Math.min(...xs), minY: Math.min(...ys) };
}

export default function CameraStage({
  zones,
  frame,
  tracks = [],
  metrics,
  mode,
  draft = [],
  selectedZoneId,
  onStageClick,
}: Props) {
  const W = frame.width;
  const H = frame.height;
  const s = Math.max(W, H) / 1000;
  const boxW = W * 0.06;
  const boxH = H * 0.26;

  // Map a screen click back to ORIGINAL IMAGE PIXELS regardless of CSS resize.
  const handleClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!onStageClick) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * W;
    const y = ((e.clientY - rect.top) / rect.height) * H;
    onStageClick({ x: Math.max(0, Math.min(W, Math.round(x))), y: Math.max(0, Math.min(H, Math.round(y))) });
  };

  return (
    <svg
      className={`stage ${mode === 'editor' ? 'stage--editor' : ''}`}
      viewBox={`0 0 ${W} ${H}`}
      style={{ aspectRatio: `${W} / ${H}`, fontFamily: 'var(--font-body)' }}
      preserveAspectRatio="none"
      onClick={handleClick}
      role="img"
      aria-label="Camera feed with monitoring zones"
    >
      {frame.url ? (
        <image href={frame.url} x={0} y={0} width={W} height={H} preserveAspectRatio="none" />
      ) : (
        <BuiltInScene w={W} h={H} />
      )}

      {/* Zones */}
      {zones.map((z) => {
        const m = metrics?.[z.id];
        const stroke = mode === 'live' && m ? STATUS_COLOR[m.status] : z.color;
        const selected = z.id === selectedZoneId;
        const bb = z.points.length ? bbox(z.points) : { minX: 0, minY: 0 };
        return (
          <g key={z.id}>
            <path
              d={polygonPath(z.points)}
              fill={stroke}
              fillOpacity={selected ? 0.22 : 0.1}
              stroke={stroke}
              strokeWidth={(selected ? 4 : 2.5) * s}
              strokeDasharray={mode === 'editor' ? `${10 * s} ${6 * s}` : `${9 * s} ${5 * s}`}
            />
            {mode === 'editor' &&
              z.points.map((p, i) => (
                <circle key={i} cx={p.x} cy={p.y} r={(selected ? 8 : 5) * s} fill={stroke} />
              ))}
            {z.points.length >= 3 && (
              <g transform={`translate(${bb.minX + 8 * s}, ${bb.minY + 8 * s}) scale(${s})`}>
                <rect x={0} y={0} width={mode === 'live' && m ? 220 : 150} height={22} rx={5} fill="rgba(8,9,11,0.82)" />
                <text x={8} y={15} fill={stroke} fontFamily="OCRAM Regular, monospace" fontSize={12} fontWeight={600}>
                  {mode === 'live' && m ? `${z.name} - ${m.status.toUpperCase()} - ${m.personCount}` : z.name}
                </text>
              </g>
            )}
          </g>
        );
      })}

      {/* In-progress polygon */}
      {draft.length > 0 && (
        <g>
          <polyline
            points={draft.map((p) => `${p.x},${p.y}`).join(' ')}
            fill="rgba(76,154,255,0.12)"
            stroke={DETECT}
            strokeWidth={2.5 * s}
            strokeDasharray={`${8 * s} ${5 * s}`}
          />
          {draft.map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r={7 * s} fill={DETECT} stroke="#fff" strokeWidth={1.5 * s} />
          ))}
        </g>
      )}

      {/* Detection bounding boxes */}
      {mode === 'live' &&
        tracks.map((t) => {
          const x = Math.max(2, Math.min(W - boxW - 2, t.x - boxW / 2));
          const y = Math.max(2, Math.min(H - boxH - 2, t.y - boxH / 2));
          return (
            <g key={t.id}>
              <rect x={x} y={y} width={boxW} height={boxH} rx={3 * s} fill="none" stroke={DETECT} strokeWidth={1.6 * s} />
              <g transform={`translate(${x}, ${y - 17 * s}) scale(${s})`}>
                <rect x={0} y={0} width={78} height={16} rx={3} fill={DETECT} />
                <text x={5} y={12} fill="#08090b" fontFamily="OCRAM Regular, monospace" fontSize={10} fontWeight={600}>
                  Person {conf(t.id)}
                </text>
              </g>
            </g>
          );
        })}
    </svg>
  );
}

/** Stylized top-down venue used when no real camera frame is uploaded. */
function BuiltInScene({ w, h }: { w: number; h: number }) {
  const grid = [];
  const step = 64;
  for (let x = 0; x <= w; x += step) grid.push(<line key={`v${x}`} x1={x} y1={0} x2={x} y2={h} stroke="#141b26" strokeWidth={1} />);
  for (let y = 0; y <= h; y += step) grid.push(<line key={`h${y}`} x1={0} y1={y} x2={w} y2={y} stroke="#141b26" strokeWidth={1} />);
  const bw = w * 0.2;
  const bh = h * 0.085;
  const by = h * 0.24;
  return (
    <g>
      <rect x={0} y={0} width={w} height={h} fill="#0c1421" />
      {grid}
      <rect x={w * 0.14} y={by} width={bw} height={bh} rx={8} fill="#141a24" stroke="#27303d" strokeWidth={2} />
      <text x={w * 0.14 + bw / 2} y={by + bh / 2 + 6} fill="#6b7684" fontSize={h * 0.03} textAnchor="middle">Booth 1</text>
      <rect x={w * 0.66} y={by} width={bw} height={bh} rx={8} fill="#141a24" stroke="#27303d" strokeWidth={2} />
      <text x={w * 0.66 + bw / 2} y={by + bh / 2 + 6} fill="#6b7684" fontSize={h * 0.03} textAnchor="middle">Booth 2</text>
    </g>
  );
}

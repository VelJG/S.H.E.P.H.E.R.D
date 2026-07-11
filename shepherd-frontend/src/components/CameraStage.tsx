import type React from 'react';
import type { Frame, Point, Track, Zone, ZoneMetric, ZoneStatus } from '../types';
import { centroid, polygonPath } from '../lib/geometry';

const STATUS_COLOR: Record<ZoneStatus, string> = {
  normal: '#22c55e',
  warning: '#ff9900',
  congested: '#ff4d4f',
};

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

  // Map a screen click back to ORIGINAL IMAGE PIXELS. rect.width/height is the
  // CSS-resized size; dividing by it and multiplying by the natural frame size
  // undoes any display scaling, so points are always in snapshot pixels.
  const handleClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!onStageClick) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * W;
    const y = ((e.clientY - rect.top) / rect.height) * H;
    onStageClick({
      x: Math.max(0, Math.min(W, Math.round(x))),
      y: Math.max(0, Math.min(H, Math.round(y))),
    });
  };

  // Scale label/vertex sizes to the frame so they look consistent at any resolution.
  const s = Math.max(W, H) / 1000;

  return (
    <svg
      className={`stage ${mode === 'editor' ? 'stage--editor' : ''}`}
      viewBox={`0 0 ${W} ${H}`}
      style={{ aspectRatio: `${W} / ${H}` }}
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

      {zones.map((z) => {
        const m = metrics?.[z.id];
        const stroke = mode === 'live' && m ? STATUS_COLOR[m.status] : z.color;
        const c = centroid(z.points);
        const selected = z.id === selectedZoneId;
        return (
          <g key={z.id}>
            <path
              d={polygonPath(z.points)}
              fill={stroke}
              fillOpacity={selected ? 0.28 : 0.16}
              stroke={stroke}
              strokeWidth={(selected ? 4 : 2.5) * s}
              strokeDasharray={mode === 'editor' ? `${10 * s} ${6 * s}` : undefined}
            />
            {z.points.map((p, i) => (
              <circle key={i} cx={p.x} cy={p.y} r={(selected ? 8 : 5) * s} fill={stroke} />
            ))}
            {z.points.length >= 3 && (
              <g transform={`translate(${c.x}, ${c.y}) scale(${s})`} textAnchor="middle">
                <rect x={-72} y={-24} width={144} height={44} rx={8} fill="rgba(12,20,33,0.82)" stroke={stroke} strokeWidth={1.5} />
                <text x={0} y={-6} fill="#fff" fontSize={17} fontWeight={600}>{z.name}</text>
                {mode === 'live' && m && (
                  <text x={0} y={14} fill={stroke} fontSize={15} fontWeight={700}>
                    {m.personCount} người · {m.status.toUpperCase()}
                  </text>
                )}
              </g>
            )}
          </g>
        );
      })}

      {draft.length > 0 && (
        <g>
          <polyline
            points={draft.map((p) => `${p.x},${p.y}`).join(' ')}
            fill="rgba(255,153,0,0.12)"
            stroke="#ff9900"
            strokeWidth={2.5 * s}
            strokeDasharray={`${8 * s} ${5 * s}`}
          />
          {draft.map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r={7 * s} fill="#ff9900" stroke="#fff" strokeWidth={1.5 * s} />
          ))}
        </g>
      )}

      {mode === 'live' &&
        tracks.map((t) => (
          <g key={t.id}>
            {t.trail.length > 1 && (
              <polyline
                points={t.trail.map((p) => `${p.x},${p.y}`).join(' ')}
                fill="none"
                stroke="#00a9e0"
                strokeOpacity={0.35}
                strokeWidth={2 * s}
              />
            )}
            <circle cx={t.x} cy={t.y} r={9 * s} fill="#00a9e0" stroke="#fff" strokeWidth={1.5 * s} />
            <text x={t.x} y={t.y - 13 * s} fill="#cfe9ff" fontSize={11 * s} textAnchor="middle">#{t.id}</text>
          </g>
        ))}
    </svg>
  );
}

/** Stylized top-down venue used when no real camera frame is uploaded. */
function BuiltInScene({ w, h }: { w: number; h: number }) {
  const grid = [];
  const step = 64;
  for (let x = 0; x <= w; x += step) grid.push(<line key={`v${x}`} x1={x} y1={0} x2={x} y2={h} stroke="#1f2a3a" strokeWidth={1} />);
  for (let y = 0; y <= h; y += step) grid.push(<line key={`h${y}`} x1={0} y1={y} x2={w} y2={y} stroke="#1f2a3a" strokeWidth={1} />);
  const bw = w * 0.2;
  const bh = h * 0.085;
  const by = h * 0.24;
  return (
    <g>
      <rect x={0} y={0} width={w} height={h} fill="#0c1421" />
      {grid}
      <rect x={w * 0.14} y={by} width={bw} height={bh} rx={8} fill="#17293b" stroke="#2b4a63" strokeWidth={2} />
      <text x={w * 0.14 + bw / 2} y={by + bh / 2 + 6} fill="#8fb7d4" fontSize={h * 0.03} textAnchor="middle">🎁 Booth 1</text>
      <rect x={w * 0.66} y={by} width={bw} height={bh} rx={8} fill="#17293b" stroke="#2b4a63" strokeWidth={2} />
      <text x={w * 0.66 + bw / 2} y={by + bh / 2 + 6} fill="#8fb7d4" fontSize={h * 0.03} textAnchor="middle">🎁 Booth 2</text>
    </g>
  );
}

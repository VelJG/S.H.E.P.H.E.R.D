import type React from 'react';
import type { Frame, Point, Track, Zone, ZoneMetric, ZoneStatus } from '../types';
import { polygonPath } from '../lib/geometry';

const STATUS_COLOR: Record<ZoneStatus, string> = {
  normal: '#46c06a',
  warning: '#d6a743',
  congested: '#ef5b47',
};

type Props = {
  zones: Zone[];
  frame: Frame;
  metrics?: Record<string, ZoneMetric>;
  tracks?: Track[];
  mode: 'live' | 'editor' | 'upload';
  draft?: Point[];
  selectedZoneId?: string | null;
  onStageClick?: (p: Point) => void;
  onSelectZone?: (id: string) => void;
};

function bbox(poly: Point[]) {
  const xs = poly.map((p) => p.x);
  const ys = poly.map((p) => p.y);
  return { minX: Math.min(...xs), minY: Math.min(...ys) };
}

export default function CameraStage({
  zones,
  frame,
  metrics,
  tracks = [],
  mode,
  draft = [],
  selectedZoneId,
  onStageClick,
  onSelectZone,
}: Props) {
  const W = frame.width;
  const H = frame.height;
  const s = Math.max(W, H) / 1000;
  const editable = mode === 'editor' || mode === 'upload';
  const showTracks = mode === 'live' || mode === 'upload';

  // Map a screen click back to ORIGINAL IMAGE PIXELS regardless of CSS resize.
  const handleClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!onStageClick) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * W;
    const y = ((e.clientY - rect.top) / rect.height) * H;
    onStageClick({ x: Math.max(0, Math.min(W, Math.round(x))), y: Math.max(0, Math.min(H, Math.round(y))) });
  };

  const isVideo = frame.kind === 'video' && !!frame.url;
  const externalBackdrop = isVideo || (mode === 'live' && !!frame.url);

  return (
    <svg
      className={`stage ${editable && onStageClick ? 'stage--editor' : ''}`}
      viewBox={`0 0 ${W} ${H}`}
      // transparent when a <video> backdrop is rendered behind the SVG by the feed
      style={{ aspectRatio: `${W} / ${H}`, fontFamily: 'var(--font-body)', background: externalBackdrop ? 'transparent' : undefined }}
      preserveAspectRatio="none"
      onClick={handleClick}
      role="img"
      aria-label="Camera feed with monitoring zones"
    >
      {externalBackdrop ? null : frame.url ? (
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
        const n = z.points.length || 1;
        const cx = z.points.reduce((a, p) => a + p.x, 0) / n;
        const cy = z.points.reduce((a, p) => a + p.y, 0) / n;
        return (
          <g key={z.id}>
            <path
              d={polygonPath(z.points)}
              fill={stroke}
              fillOpacity={selected ? 0.24 : 0.14}
              stroke={stroke}
              strokeWidth={(selected ? 4 : 2.5) * s}
              strokeDasharray={editable ? undefined : `${9 * s} ${5 * s}`}
              onClick={editable && onSelectZone ? (e) => { e.stopPropagation(); onSelectZone(z.id); } : undefined}
              style={editable ? { cursor: 'pointer' } : undefined}
            />
            {/* editor: show vertices only for the selected zone */}
            {editable &&
              selected &&
              z.points.map((p, i) => (
                <circle key={i} cx={p.x} cy={p.y} r={7 * s} fill={stroke} stroke="#fff" strokeWidth={2 * s} />
              ))}
            {/* live: status pill at top-left of the zone */}
            {z.points.length >= 3 && (mode === 'live' || mode === 'upload') && m && (
              <g transform={`translate(${bb.minX + 8 * s}, ${bb.minY + 8 * s}) scale(${s})`}>
                <rect x={0} y={0} width={220} height={22} rx={5} fill="rgba(8,9,11,0.82)" />
                <text x={8} y={15} fill={stroke} fontFamily="OCRAM Regular, monospace" fontSize={12} fontWeight={600}>
                  {z.name} - {m.status.toUpperCase()} - {m.personCount}
                </text>
              </g>
            )}
            {/* editor: big centered zone name */}
            {z.points.length >= 3 && editable && !m && (
              <text
                x={cx}
                y={cy}
                fill="#fff"
                fontFamily="OCRAM Regular, sans-serif"
                fontSize={22 * s}
                fontWeight={700}
                textAnchor="middle"
                dominantBaseline="middle"
                stroke="rgba(8,9,11,.85)"
                strokeWidth={5 * s}
                style={{ paintOrder: 'stroke', pointerEvents: 'none' }}
              >
                {z.name}
              </text>
            )}
          </g>
        );
      })}

      {/* ByteTrack IDs and bottom-center foot points */}
      {showTracks && tracks.map((track) => {
        const [x1, y1, x2, y2] = track.bbox_xyxy;
        const labelY = Math.max(0, y1 - 23 * s);
        return (
          <g key={track.id} pointerEvents="none">
            <rect x={x1} y={y1} width={Math.max(0, x2 - x1)} height={Math.max(0, y2 - y1)} fill="none" stroke="#f7b955" strokeWidth={2.5 * s} />
            <rect x={x1} y={labelY} width={92 * s} height={22 * s} rx={4 * s} fill="#f7b955" />
            <text x={x1 + 7 * s} y={labelY + 15 * s} fill="#08090b" fontFamily="OCRAM Regular, monospace" fontSize={12 * s} fontWeight={700}>
              ID {track.id} - {Math.round(track.confidence * 100)}%
            </text>
            <circle cx={(x1 + x2) / 2} cy={y2} r={4 * s} fill="#fff" stroke="#f7b955" strokeWidth={2 * s} />
          </g>
        );
      })}

      {/* In-progress polygon */}
      {draft.length > 0 && (
        <g>
          <polyline
            points={draft.map((p) => `${p.x},${p.y}`).join(' ')}
            fill="rgba(214,167,67,0.12)"
            stroke="#d6a743"
            strokeWidth={3 * s}
            strokeDasharray={`${14 * s} ${9 * s}`}
            style={{ pointerEvents: 'none' }}
          />
          {draft.map((p, i) => {
            const last = i === draft.length - 1;
            return (
              <circle
                key={i}
                cx={p.x}
                cy={p.y}
                r={(last ? 9 : 7) * s}
                fill={last ? '#fff' : '#d6a743'}
                stroke={last ? '#d6a743' : '#fff'}
                strokeWidth={(last ? 3 : 2) * s}
                style={{ pointerEvents: 'none' }}
              />
            );
          })}
        </g>
      )}

    </svg>
  );
}

/** Stylized top-down venue used when no real camera frame is uploaded. */
function BuiltInScene({ w, h }: { w: number; h: number }) {
  const grid = [];
  const step = 64;
  for (let x = 0; x <= w; x += step) grid.push(<line key={`v${x}`} x1={x} y1={0} x2={x} y2={h} stroke="#141b26" strokeWidth={1} />);
  for (let y = 0; y <= h; y += step) grid.push(<line key={`h${y}`} x1={0} y1={y} x2={w} y2={y} stroke="#141b26" strokeWidth={1} />);
  return (
    <g>
      <rect x={0} y={0} width={w} height={h} fill="#0c1421" />
      {grid}
    </g>
  );
}



import type { Frame, Zone } from '../types';

const KEY = 'shepherd.zones.v1';

/** Two default gift-booth queue zones, authored in the default 1280x720 frame. */
export function defaultZones(): Zone[] {
  return [
    {
      id: 'booth-1',
      name: 'Quầy quà 1',
      color: '#00A9E0',
      points: [
        { x: 150, y: 300 },
        { x: 470, y: 300 },
        { x: 470, y: 690 },
        { x: 150, y: 690 },
      ],
      warnAt: 4,
      congestAt: 7,
      avgServiceSec: 20,
    },
    {
      id: 'booth-2',
      name: 'Quầy quà 2',
      color: '#FF9900',
      points: [
        { x: 810, y: 300 },
        { x: 1130, y: 300 },
        { x: 1130, y: 690 },
        { x: 810, y: 690 },
      ],
      warnAt: 4,
      congestAt: 7,
      avgServiceSec: 20,
    },
  ];
}

export function loadZones(): Zone[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return defaultZones();
    const parsed = JSON.parse(raw) as Zone[];
    if (!Array.isArray(parsed) || parsed.length === 0) return defaultZones();
    return parsed;
  } catch {
    return defaultZones();
  }
}

export function saveZones(zones: Zone[]): void {
  localStorage.setItem(KEY, JSON.stringify(zones));
}

/**
 * Export shape the Python processor consumes. Points are in ORIGINAL IMAGE
 * PIXELS relative to frameWidth x frameHeight — the processor scales them to
 * whatever resolution its decoded frame happens to be.
 */
export function exportForProcessor(zones: Zone[], frame: Frame) {
  return {
    frameWidth: frame.width,
    frameHeight: frame.height,
    zones: zones.map((z) => ({
      id: z.id,
      name: z.name,
      warnAt: z.warnAt,
      congestAt: z.congestAt,
      avgServiceSec: z.avgServiceSec,
      points: z.points.map((p) => [Math.round(p.x), Math.round(p.y)]),
    })),
  };
}

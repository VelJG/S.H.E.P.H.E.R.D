import type { Frame, Zone } from '../types';

const KEY = 'shepherd.zones.v3';

/** The editor starts empty — the operator draws the zones they need. */
export function defaultZones(): Zone[] {
  return [];
}

export function loadZones(): Zone[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return defaultZones();
    const parsed = JSON.parse(raw) as Zone[];
    if (!Array.isArray(parsed)) return defaultZones();
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
 * PIXELS relative to frameWidth x frameHeight - the processor scales them to
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

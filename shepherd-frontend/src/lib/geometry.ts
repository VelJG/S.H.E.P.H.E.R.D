import type { Point } from '../types';

/** Ray-casting point-in-polygon test. This is the heart of zone counting:
 *  a person is "in" a zone when their point falls inside the drawn polygon. */
export function pointInPolygon(p: Point, poly: Point[]): boolean {
  if (poly.length < 3) return false;
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i].x;
    const yi = poly[i].y;
    const xj = poly[j].x;
    const yj = poly[j].y;
    const intersect =
      yi > p.y !== yj > p.y &&
      p.x < ((xj - xi) * (p.y - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

/** Centroid of a polygon, used to place the zone label. */
export function centroid(poly: Point[]): Point {
  if (poly.length === 0) return { x: 0, y: 0 };
  const s = poly.reduce(
    (acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }),
    { x: 0, y: 0 },
  );
  return { x: s.x / poly.length, y: s.y / poly.length };
}

export function polygonPath(poly: Point[]): string {
  if (poly.length === 0) return '';
  return poly.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ') + ' Z';
}

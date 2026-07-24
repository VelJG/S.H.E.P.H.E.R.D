import type { Track, Zone, ZoneStatus } from '../types';

export type HeatmapUpdate = {
  zones: Record<string, { heatMean: number; heatMax: number; activeTrackIds: number[]; status: ZoneStatus }>;
  alerts: string[];
};

const env = (import.meta as any).env ?? {};
const numberEnv = (name: string, fallback: number) => {
  const value = Number(env[name]);
  return Number.isFinite(value) ? value : fallback;
};
const SCALE = numberEnv('VITE_HEATMAP_SCALE', 0.25);
const DECAY_SECONDS = numberEnv('VITE_HEAT_DECAY_SECONDS', 5);
const INCREMENT = numberEnv('VITE_HEAT_INCREMENT', 1);
const RADIUS = numberEnv('VITE_HEAT_RADIUS', 25);
const SIGMA = numberEnv('VITE_HEAT_SIGMA', 12);
const MAX_HEAT = numberEnv('VITE_HEAT_MAX', 5);
const ALPHA = numberEnv('VITE_HEAT_ALPHA', 0.55);
const HEAT_THRESHOLD = numberEnv('VITE_HEAT_CONGESTION_THRESHOLD', 0.15);
const PERSIST_SECONDS = numberEnv('VITE_CONGESTION_PERSIST_SECONDS', 5);
const COOLDOWN_SECONDS = numberEnv('VITE_ALERT_COOLDOWN_SECONDS', 60);
const MODE = env.VITE_HEATMAP_MODE === 'zones' ? 'zones' : 'global';

export class TemporalHeatmap {
  private heat = new Float32Array();
  private width = 0;
  private height = 0;
  private lastTime: number | null = null;
  private kernel = this.makeKernel();
  private masks = new Map<string, Uint8Array>();
  private maskKey = '';
  private conditionSince = new Map<string, number>();
  private lastAlert = new Map<string, number>();
  private display = document.createElement('canvas');

  reset(canvas?: HTMLCanvasElement | null) {
    this.heat = new Float32Array(this.width * this.height);
    this.lastTime = null;
    this.conditionSince.clear();
    this.lastAlert.clear();
    canvas?.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height);
  }

  update(canvas: HTMLCanvasElement, tracks: Track[], zones: Zone[], frameWidth: number, frameHeight: number, now: number): HeatmapUpdate {
    this.ensureSize(frameWidth, frameHeight);
    this.ensureMasks(zones);
    const dt = this.lastTime === null ? 0.1 : Math.max(0, now - this.lastTime);
    this.lastTime = now;
    const decay = Math.exp(-dt / Math.max(0.01, DECAY_SECONDS));
    for (let i = 0; i < this.heat.length; i++) this.heat[i] *= decay;
    for (const track of tracks) {
      if (track.class_id !== 0 || !Number.isFinite(track.id)) continue;
      const point = footPoint(track, frameWidth, frameHeight);
      if (MODE === 'zones' && !zones.some((zone) => pointInPolygon(point, zone.points))) continue;
      this.addKernel(point.x * SCALE, point.y * SCALE, INCREMENT * Math.min(dt, 1));
    }
    if (MODE === 'zones') this.clipToZones();
    this.draw(canvas, frameWidth, frameHeight);

    const result: HeatmapUpdate['zones'] = {};
    const alerts: string[] = [];
    for (const zone of zones) {
      const active = tracks.filter((track) => track.class_id === 0 && trackIntersectsZone(track, zone, frameWidth, frameHeight)).map((track) => track.id);
      const mask = this.masks.get(zone.id);
      let sum = 0, max = 0, count = 0;
      if (mask) for (let i = 0; i < mask.length; i++) if (mask[i]) { sum += this.heat[i]; max = Math.max(max, this.heat[i]); count++; }
      const mean = Math.min(1, count ? sum / count / MAX_HEAT : 0);
      const peak = Math.min(1, max / MAX_HEAT);
      const condition = active.length >= zone.congestAt && mean >= HEAT_THRESHOLD;
      const since = condition ? (this.conditionSince.get(zone.id) ?? now) : now;
      if (condition) this.conditionSince.set(zone.id, since); else this.conditionSince.delete(zone.id);
      const congested = condition && now - since >= PERSIST_SECONDS;
      if (congested && now - (this.lastAlert.get(zone.id) ?? -Infinity) >= COOLDOWN_SECONDS) {
        this.lastAlert.set(zone.id, now);
        alerts.push(zone.id);
      }
      result[zone.id] = {
        heatMean: mean,
        heatMax: peak,
        activeTrackIds: active,
        status: congested ? 'congested' : active.length >= zone.warnAt || condition ? 'warning' : 'normal',
      };
    }
    return { zones: result, alerts };
  }

  private ensureSize(frameWidth: number, frameHeight: number) {
    const width = Math.max(1, Math.round(frameWidth * SCALE));
    const height = Math.max(1, Math.round(frameHeight * SCALE));
    if (width === this.width && height === this.height) return;
    this.width = width;
    this.height = height;
    this.heat = new Float32Array(width * height);
    this.maskKey = '';
    this.lastTime = null;
  }

  private makeKernel() {
    const radius = Math.max(1, Math.round(RADIUS * SCALE));
    const sigma = Math.max(0.1, SIGMA * SCALE);
    const size = radius * 2 + 1;
    const values = new Float32Array(size * size);
    for (let y = -radius; y <= radius; y++) for (let x = -radius; x <= radius; x++)
      values[(y + radius) * size + x + radius] = Math.exp(-(x * x + y * y) / (2 * sigma * sigma));
    return { radius, size, values };
  }

  private addKernel(cx: number, cy: number, increment: number) {
    const { radius, size, values } = this.kernel;
    const centerX = Math.round(cx), centerY = Math.round(cy);
    for (let ky = -radius; ky <= radius; ky++) {
      const y = centerY + ky;
      if (y < 0 || y >= this.height) continue;
      for (let kx = -radius; kx <= radius; kx++) {
        const x = centerX + kx;
        if (x >= 0 && x < this.width) this.heat[y * this.width + x] += values[(ky + radius) * size + kx + radius] * increment;
      }
    }
  }

  private ensureMasks(zones: Zone[]) {
    const key = `${this.width}x${this.height}:${zones.map((z) => `${z.id}:${z.points.map((p) => `${p.x},${p.y}`).join(';')}`).join('|')}`;
    if (key === this.maskKey) return;
    this.maskKey = key;
    this.masks.clear();
    for (const zone of zones) {
      const canvas = document.createElement('canvas');
      canvas.width = this.width;
      canvas.height = this.height;
      const ctx = canvas.getContext('2d')!;
      if (zone.points.length >= 3) {
        ctx.beginPath();
        zone.points.forEach((p, i) => i ? ctx.lineTo(p.x * SCALE, p.y * SCALE) : ctx.moveTo(p.x * SCALE, p.y * SCALE));
        ctx.closePath();
        ctx.fillStyle = '#fff';
        ctx.fill();
      }
      const pixels = ctx.getImageData(0, 0, this.width, this.height).data;
      this.masks.set(zone.id, Uint8Array.from({ length: this.heat.length }, (_, i) => pixels[i * 4 + 3] ? 1 : 0));
    }
  }

  private clipToZones() {
    const masks = [...this.masks.values()];
    for (let i = 0; i < this.heat.length; i++) if (!masks.some((mask) => mask[i])) this.heat[i] = 0;
  }

  private draw(canvas: HTMLCanvasElement, frameWidth: number, frameHeight: number) {
    this.display.width = this.width;
    this.display.height = this.height;
    const ctx = this.display.getContext('2d')!;
    const image = ctx.createImageData(this.width, this.height);
    for (let i = 0; i < this.heat.length; i++) {
      const value = Math.min(1, this.heat[i] / MAX_HEAT);
      const [r, g, b] = inferno(value);
      image.data.set([r, g, b, value < 0.002 ? 0 : Math.round(255 * ALPHA * Math.min(1, Math.sqrt(value) * 1.5))], i * 4);
    }
    ctx.putImageData(image, 0, 0);
    canvas.width = frameWidth;
    canvas.height = frameHeight;
    const output = canvas.getContext('2d')!;
    output.clearRect(0, 0, frameWidth, frameHeight);
    output.imageSmoothingEnabled = true;
    output.drawImage(this.display, 0, 0, frameWidth, frameHeight);
  }
}

function footPoint(track: Track, width: number, height: number) {
  const [x1, , x2, y2] = track.bbox_xyxy;
  return { x: Math.max(0, Math.min(width - 1, (x1 + x2) / 2)), y: Math.max(0, Math.min(height - 1, y2)) };
}

function clampPoint(point: { x: number; y: number }, width: number, height: number) {
  return {
    x: Math.max(0, Math.min(width - 1, point.x)),
    y: Math.max(0, Math.min(height - 1, point.y)),
  };
}

function bboxPoints(track: Track, width: number, height: number) {
  const [x1, y1, x2, y2] = track.bbox_xyxy;
  const cx = (x1 + x2) / 2;
  const cy = (y1 + y2) / 2;
  return [
    { x: cx, y: y2 },
    { x: cx, y: cy },
    { x: x1, y: cy },
    { x: x2, y: cy },
    { x: x1, y: y2 },
    { x: x2, y: y2 },
  ].map((point) => clampPoint(point, width, height));
}

function trackIntersectsZone(track: Track, zone: Zone, width: number, height: number) {
  if (zone.points.length < 3) return false;
  const [x1, y1, x2, y2] = track.bbox_xyxy;
  if (bboxPoints(track, width, height).some((point) => pointInPolygon(point, zone.points))) return true;
  return zone.points.some((point) => point.x >= x1 && point.x <= x2 && point.y >= y1 && point.y <= y2);
}

export function pointInPolygon(point: { x: number; y: number }, polygon: { x: number; y: number }[]) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i], b = polygon[j];
    if ((a.y > point.y) !== (b.y > point.y) && point.x < ((b.x - a.x) * (point.y - a.y)) / (b.y - a.y) + a.x) inside = !inside;
  }
  return inside;
}

function inferno(value: number): [number, number, number] {
  const stops: [number, number, number][] = [[0, 0, 4], [87, 15, 109], [187, 55, 84], [249, 142, 8], [252, 255, 164]];
  const scaled = Math.min(0.9999, Math.max(0, value)) * (stops.length - 1);
  const index = Math.floor(scaled), mix = scaled - index;
  return stops[index].map((v, channel) => Math.round(v + (stops[index + 1][channel] - v) * mix)) as [number, number, number];
}

if (env.DEV) console.assert(pointInPolygon({ x: 5, y: 5 }, [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }]));

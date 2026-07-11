import { useEffect, useRef, useState } from 'react';
import type { Incident, Track, Zone, ZoneMetric, ZoneStatus } from '../types';
import { centroid, pointInPolygon } from './geometry';

const TICK_MS = 500;
const N_PEOPLE = 16;
const CONGEST_HOLD_TICKS = 4; // must stay congested this long before an incident fires
const HISTORY_LEN = 28;

type Agent = Track & { tx: number; ty: number; speed: number };

function statusFor(count: number, z: Zone): ZoneStatus {
  if (count >= z.congestAt) return 'congested';
  if (count >= z.warnAt) return 'warning';
  return 'normal';
}

// Bias targets toward booth 2 so the demo reliably produces a congestion event.
function pickTarget(zones: Zone[], w: number, h: number): { x: number; y: number } {
  const r = Math.random();
  if (zones.length >= 2 && r < 0.5) {
    const c = centroid(zones[1].points);
    return { x: c.x + (Math.random() - 0.5) * 180, y: c.y + (Math.random() - 0.5) * 220 };
  }
  if (zones.length >= 1 && r < 0.75) {
    const c = centroid(zones[0].points);
    return { x: c.x + (Math.random() - 0.5) * 200, y: c.y + (Math.random() - 0.5) * 240 };
  }
  return { x: 0.08 * w + Math.random() * 0.84 * w, y: 0.05 * h + Math.random() * 0.25 * h };
}

function makeAgents(zones: Zone[], w: number, h: number): Agent[] {
  return Array.from({ length: N_PEOPLE }, (_, i) => {
    const t = pickTarget(zones, w, h);
    return {
      id: i + 1,
      x: 0.08 * w + Math.random() * 0.84 * w,
      y: 0.06 * h + Math.random() * 0.88 * h,
      trail: [],
      tx: t.x,
      ty: t.y,
      speed: (12 + Math.random() * 12) * (Math.max(w, h) / 1000),
    };
  });
}

export type SimState = {
  tracks: Track[];
  metrics: Record<string, ZoneMetric>;
  incidents: Incident[];
  history: { counts: Record<string, number> }[];
  running: boolean;
  setRunning: (v: boolean) => void;
  ackIncident: (id: string) => void;
  resolveIncident: (id: string) => void;
};

export function useSimulation(zones: Zone[], frameW: number, frameH: number): SimState {
  const agents = useRef<Agent[]>(makeAgents(zones, frameW, frameH));
  const congestStreak = useRef<Record<string, number>>({});
  const openZones = useRef<Set<string>>(new Set());

  const [tracks, setTracks] = useState<Track[]>([]);
  const [metrics, setMetrics] = useState<Record<string, ZoneMetric>>({});
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [history, setHistory] = useState<{ counts: Record<string, number> }[]>([]);
  const [running, setRunning] = useState(true);

  // Keep the latest zones reachable from the interval without restarting it.
  const zonesRef = useRef(zones);
  zonesRef.current = zones;

  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => {
      const zs = zonesRef.current;
      const list = agents.current;

      for (const a of list) {
        const dx = a.tx - a.x;
        const dy = a.ty - a.y;
        const dist = Math.hypot(dx, dy) || 1;
        if (dist < 28) {
          const t = pickTarget(zs, frameW, frameH);
          a.tx = t.x;
          a.ty = t.y;
        } else {
          a.x += (dx / dist) * a.speed + (Math.random() - 0.5) * 5;
          a.y += (dy / dist) * a.speed + (Math.random() - 0.5) * 5;
          a.x = Math.max(20, Math.min(frameW - 20, a.x));
          a.y = Math.max(20, Math.min(frameH - 20, a.y));
        }
        a.trail = [...a.trail, { x: a.x, y: a.y }].slice(-6);
      }

      const nextMetrics: Record<string, ZoneMetric> = {};
      const counts: Record<string, number> = {};
      for (const z of zs) {
        const count = list.filter((a) => pointInPolygon(a, z.points)).length;
        const status = statusFor(count, z);
        counts[z.id] = count;
        nextMetrics[z.id] = {
          zoneId: z.id,
          personCount: count,
          waitSec: count * z.avgServiceSec,
          status,
        };

        // Debounced incident creation: congested must hold for several ticks.
        const streak = status === 'congested' ? (congestStreak.current[z.id] ?? 0) + 1 : 0;
        congestStreak.current[z.id] = streak;
        if (streak >= CONGEST_HOLD_TICKS && !openZones.current.has(z.id)) {
          openZones.current.add(z.id);
          setIncidents((prev) => [
            {
              id: `INC-${Date.now().toString().slice(-6)}`,
              zoneId: z.id,
              zoneName: z.name,
              personCount: count,
              createdAt: Date.now(),
              status: 'open' as const,
            },
            ...prev,
          ].slice(0, 20));
        }
      }

      setTracks(list.map((a) => ({ id: a.id, x: a.x, y: a.y, trail: a.trail })));
      setMetrics(nextMetrics);
      setHistory((prev) => [...prev, { counts }].slice(-HISTORY_LEN));
    }, TICK_MS);
    return () => clearInterval(timer);
  }, [running, frameW, frameH]);

  const ackIncident = (id: string) =>
    setIncidents((prev) =>
      prev.map((i) => (i.id === id ? { ...i, status: 'acknowledged' } : i)),
    );

  const resolveIncident = (id: string) =>
    setIncidents((prev) => {
      const target = prev.find((i) => i.id === id);
      if (target) openZones.current.delete(target.zoneId); // allow re-alerting later
      return prev.map((i) => (i.id === id ? { ...i, status: 'resolved' } : i));
    });

  return { tracks, metrics, incidents, history, running, setRunning, ackIncident, resolveIncident };
}

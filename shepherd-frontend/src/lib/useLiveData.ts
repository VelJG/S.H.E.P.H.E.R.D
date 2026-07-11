import { useCallback, useEffect, useRef, useState } from 'react';
import type { Incident, Zone, ZoneMetric, ZoneStatus } from '../types';

const API = (import.meta as any).env?.VITE_API_URL ?? '';
const POLL_MS = 1500;
const HISTORY_LEN = 28;

const VALID_STATUS: ZoneStatus[] = ['normal', 'warning', 'congested'];
function asStatus(v: unknown): ZoneStatus {
  return VALID_STATUS.includes(v as ZoneStatus) ? (v as ZoneStatus) : 'normal';
}
function num(v: unknown): number {
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
}

export type LiveState = {
  metrics: Record<string, ZoneMetric>;
  incidents: Incident[];
  history: { total: number }[];
  connected: boolean;
  running: boolean;
  setRunning: (v: boolean) => void;
  ackIncident: (id: string) => void;
  resolveIncident: (id: string) => void;
};

/**
 * Polls the real backend (API Gateway) for live metrics + incidents.
 * `zones` is only used to resolve zoneId -> human name for incident cards.
 */
export function useLiveData(zones: Zone[]): LiveState {
  const [metrics, setMetrics] = useState<Record<string, ZoneMetric>>({});
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [history, setHistory] = useState<{ total: number }[]>([]);
  const [connected, setConnected] = useState(false);
  const [running, setRunning] = useState(true);

  const zonesRef = useRef(zones);
  zonesRef.current = zones;

  const poll = useCallback(async () => {
    try {
      const [mRes, iRes] = await Promise.all([
        fetch(`${API}/metrics/latest`),
        fetch(`${API}/incidents`),
      ]);
      if (!mRes.ok || !iRes.ok) throw new Error('bad status');
      const mJson = await mRes.json();
      const iJson = await iRes.json();

      const nameOf = (zid: string) =>
        zonesRef.current.find((z) => z.id === zid)?.name ?? zid;

      const nextMetrics: Record<string, ZoneMetric> = {};
      let total = 0;
      for (const it of mJson.items ?? []) {
        const zoneId = String(it.zoneId ?? '');
        if (!zoneId) continue;
        const personCount = num(it.personCount ?? it.occupancy);
        total += personCount;
        nextMetrics[zoneId] = {
          zoneId,
          personCount,
          waitSec: num(it.waitSec),
          status: asStatus(it.status),
        };
      }

      const nextIncidents: Incident[] = (iJson.items ?? []).map((it: any) => ({
        id: String(it.incidentId ?? it.id ?? ''),
        zoneId: String(it.zoneId ?? ''),
        zoneName: nameOf(String(it.zoneId ?? '')),
        personCount: num(it.personCount ?? it.metrics?.personCount),
        createdAt: Date.parse(it.createdAt ?? '') || Date.now(),
        status: (['open', 'acknowledged', 'resolved'].includes(it.status)
          ? it.status
          : 'open') as Incident['status'],
      }));

      setMetrics(nextMetrics);
      setIncidents(nextIncidents);
      setHistory((prev) => [...prev, { total }].slice(-HISTORY_LEN));
      setConnected(true);
    } catch {
      setConnected(false);
    }
  }, []);

  useEffect(() => {
    if (!running) return;
    poll();
    const t = setInterval(poll, POLL_MS);
    return () => clearInterval(t);
  }, [running, poll]);

  const patchIncident = async (id: string, status: Incident['status']) => {
    // optimistic update, then persist
    setIncidents((prev) => prev.map((i) => (i.id === id ? { ...i, status } : i)));
    try {
      await fetch(`${API}/incidents/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });
    } catch {
      /* next poll reconciles */
    }
  };

  return {
    metrics,
    incidents,
    history,
    connected,
    running,
    setRunning,
    ackIncident: (id) => patchIncident(id, 'acknowledged'),
    resolveIncident: (id) => patchIncident(id, 'resolved'),
  };
}

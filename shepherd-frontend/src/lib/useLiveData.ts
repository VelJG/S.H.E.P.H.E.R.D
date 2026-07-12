import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import type { Frame, Incident, Track, Zone, ZoneMetric, ZoneStatus } from '../types';
import { TemporalHeatmap } from './temporalHeatmap';

const env = (import.meta as any).env ?? {};
const API_URL = env.VITE_API_URL || '';
const YOLO_URL = env.VITE_YOLO_URL || (API_URL ? `${API_URL}/demo/infer-frame` : '/api/yolo/invocations');
const TRACK_URL = env.VITE_TRACKER_URL || (API_URL ? `${API_URL}/demo/track` : '/api/tracker/track');
const RESET_URL = TRACK_URL.replace(/\/track\/?$/, '/reset');
const HISTORY_LEN = 28;

const num = (value: unknown) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

export type LiveState = {
  metrics: Record<string, ZoneMetric>;
  tracks: Track[];
  incidents: Incident[];
  history: { total: number }[];
  connected: boolean;
  processing: boolean;
  error: string;
  latencyMs: number;
  running: boolean;
  intervalMs: number;
  setRunning: (value: boolean) => void;
  setIntervalMs: (value: number) => void;
  reset: () => Promise<void>;
  ackIncident: (id: string) => void;
  resolveIncident: (id: string) => void;
};

export function useLiveData(
  zones: Zone[],
  frame: Frame,
  videoRef: RefObject<HTMLVideoElement>,
  heatCanvasRef: RefObject<HTMLCanvasElement>,
  options: { initialRunning?: boolean; snapshotUrl?: string } = {},
): LiveState {
  const [metrics, setMetrics] = useState<Record<string, ZoneMetric>>({});
  const [tracks, setTracks] = useState<Track[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [history, setHistory] = useState<{ total: number }[]>([]);
  const [connected, setConnected] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');
  const [latencyMs, setLatencyMs] = useState(0);
  const [running, setRunning] = useState(options.initialRunning ?? true);
  const [intervalMs, setIntervalMsState] = useState(() => Math.max(1, num(env.VITE_VISION_INTERVAL_MS) || 300));
  const snapshotUrl = options.snapshotUrl ?? '';
  const zonesRef = useRef(zones);
  const busyRef = useRef(false);
  const captureRef = useRef<HTMLCanvasElement | null>(null);
  const heatmapRef = useRef<TemporalHeatmap | null>(null);
  zonesRef.current = zones;
  if (!heatmapRef.current) heatmapRef.current = new TemporalHeatmap();

  const capture = useCallback(async () => {
    if (snapshotUrl) {
      const url = new URL(snapshotUrl, window.location.href);
      url.searchParams.set('_shepherdTs', String(Date.now()));
      const response = await fetch(url.toString(), { cache: 'no-store' });
      if (!response.ok) throw new Error(`Could not read live camera snapshot: HTTP ${response.status}`);
      return response.blob();
    }
    if (!frame.url) throw new Error('Upload an image or video in Zone Editor first.');
    if (frame.kind === 'image') {
      const response = await fetch(frame.url);
      if (!response.ok) throw new Error('Could not read the uploaded image.');
      return response.blob();
    }
    const video = videoRef.current;
    if (!video || video.readyState < 2) throw new Error('Waiting for the video frame.');
    const canvas = captureRef.current ?? document.createElement('canvas');
    captureRef.current = canvas;
    canvas.width = frame.width;
    canvas.height = frame.height;
    canvas.getContext('2d')!.drawImage(video, 0, 0, frame.width, frame.height);
    return new Promise<Blob>((resolve, reject) =>
      canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('Could not capture the video frame.')), 'image/jpeg', 0.88),
    );
  }, [frame, snapshotUrl, videoRef]);

  const tick = useCallback(async () => {
    if (busyRef.current || !frame.url || !heatCanvasRef.current) return;
    busyRef.current = true;
    setProcessing(true);
    const started = performance.now();
    try {
      const blob = await capture();
      const form = new FormData();
      form.append('file', blob, 'frame.jpg');
      const yoloResponse = await fetch(YOLO_URL, { method: 'POST', body: form });
      const yoloText = await yoloResponse.text();
      if (!yoloResponse.ok) throw new Error(`YOLO ${yoloResponse.status}: ${yoloText.slice(0, 160)}`);
      const yolo = JSON.parse(yoloText);
      const detections = Array.isArray(yolo.detections) ? yolo.detections : [];

      const activeZones = zonesRef.current;
      const trackerResponse = await fetch(TRACK_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          detections,
          zones: activeZones.map((zone) => ({
            id: zone.id,
            points: zone.points.map((point) => [point.x, point.y]),
            warnAt: zone.warnAt,
            congestAt: zone.congestAt,
            avgServiceSec: zone.avgServiceSec,
          })),
        }),
      });
      const trackerText = await trackerResponse.text();
      if (!trackerResponse.ok) throw new Error(`ByteTrack ${trackerResponse.status}: ${trackerText.slice(0, 160)}`);
      const tracked = JSON.parse(trackerText);
      const nextTracks = (Array.isArray(tracked.tracks) ? tracked.tracks : []) as Track[];
      const heat = heatmapRef.current!.update(
        heatCanvasRef.current,
        nextTracks,
        activeZones,
        frame.width,
        frame.height,
        performance.now() / 1000,
      );

      const nextMetrics: Record<string, ZoneMetric> = {};
      let total = 0;
      for (const zone of activeZones) {
        const backend = (tracked.zones ?? []).find((item: any) => String(item.zoneId) === zone.id) ?? {};
        const temporal = heat.zones[zone.id];
        const personCount = num(backend.personCount ?? temporal?.activeTrackIds.length);
        total += personCount;
        nextMetrics[zone.id] = {
          zoneId: zone.id,
          personCount,
          waitSec: num(backend.waitSec ?? personCount * zone.avgServiceSec),
          status: (temporal?.status ?? backend.status ?? 'normal') as ZoneStatus,
          heatMean: temporal?.heatMean ?? 0,
          heatMax: temporal?.heatMax ?? 0,
          activeTrackIds: temporal?.activeTrackIds ?? [],
        };
      }

      if (heat.alerts.length && API_URL) {
        for (const zoneId of heat.alerts) {
          const zone = activeZones.find((item) => item.id === zoneId);
          const metric = nextMetrics[zoneId];
          void fetch(`${API_URL}/incidents`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              zoneId,
              type: 'congestion',
              severity: 'high',
              title: 'Hottest zone detected',
              summary: `${zone?.name ?? zoneId} is crowded and requires attention.`,
              personCount: metric?.personCount ?? 0,
              createdAt: new Date().toISOString(),
              notifyDiscord: true,
              metrics: {
                personCount: metric?.personCount ?? 0,
                waitSec: metric?.waitSec ?? 0,
                status: metric?.status ?? 'congested',
                heatMean: metric?.heatMean ?? 0,
                heatMax: metric?.heatMax ?? 0,
                activeTrackIds: metric?.activeTrackIds ?? [],
              },
            }),
          }).catch(() => {
            /* local incident still appears; backend/Discord can recover on next alert */
          });
        }
      }

      if (heat.alerts.length) setIncidents((previous) => {
        const next = [...previous];
        for (const zoneId of heat.alerts) {
          if (next.some((incident) => incident.zoneId === zoneId && incident.status !== 'resolved')) continue;
          const zone = activeZones.find((item) => item.id === zoneId);
          next.unshift({
            id: `HEAT-${Date.now()}-${zoneId}`,
            zoneId,
            zoneName: zone?.name ?? zoneId,
            personCount: nextMetrics[zoneId]?.personCount ?? 0,
            createdAt: Date.now(),
            status: 'open',
          });
        }
        return next;
      });
      setTracks(nextTracks);
      setMetrics(nextMetrics);
      setHistory((previous) => [...previous, { total }].slice(-HISTORY_LEN));
      setLatencyMs(Math.round(performance.now() - started));
      setConnected(true);
      setError('');
    } catch (reason) {
      setConnected(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      busyRef.current = false;
      setProcessing(false);
    }
  }, [capture, frame, heatCanvasRef]);

  const reset = useCallback(async () => {
    heatmapRef.current?.reset(heatCanvasRef.current);
    setTracks([]);
    setMetrics({});
    setHistory([]);
    setConnected(false);
    setError('');
    try { await fetch(RESET_URL, { method: 'POST' }); } catch { /* next tick reports connectivity */ }
  }, [heatCanvasRef]);

  useEffect(() => { void reset(); }, [frame.url, reset, snapshotUrl]);
  useEffect(() => {
    if (!running || !frame.url) return;
    void tick();
    const timer = window.setInterval(() => void tick(), intervalMs);
    return () => window.clearInterval(timer);
  }, [running, frame.url, intervalMs, tick]);

  const patchIncident = (id: string, status: Incident['status']) =>
    setIncidents((previous) => previous.map((incident) => incident.id === id ? { ...incident, status } : incident));

  return {
    metrics,
    tracks,
    incidents,
    history,
    connected,
    processing,
    error,
    latencyMs,
    running,
    intervalMs,
    setRunning,
    setIntervalMs: (value) => setIntervalMsState(Math.max(1, Number.isFinite(value) ? value : 300)),
    reset,
    ackIncident: (id) => patchIncident(id, 'acknowledged'),
    resolveIncident: (id) => patchIncident(id, 'resolved'),
  };
}

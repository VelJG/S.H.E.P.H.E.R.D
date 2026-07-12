import { useEffect, useRef, useState } from 'react';
import type { Frame, Point, Zone, ZoneMetric, ZoneStatus } from '../types';
import { DEFAULT_FRAME_H, DEFAULT_FRAME_W } from '../types';
import CameraStage from './CameraStage';
import { exportForProcessor } from '../lib/storage';
import { useLiveData } from '../lib/useLiveData';

const UPLOAD_VIDEO_ZONES_KEY = 'shepherd.uploadVideo.zones.v1';
const PALETTE = ['#4c9aff', '#d6a743', '#8b5cf6', '#2dd4bf', '#f472b6', '#fb923c'];

const STATUS_COLOR: Record<ZoneStatus, string> = {
  normal: '#46c06a',
  warning: '#d6a743',
  congested: '#ef5b47',
};

type SaveStatus = 'idle' | 'saved';

function loadUploadVideoZones(): Zone[] {
  try {
    const raw = localStorage.getItem(UPLOAD_VIDEO_ZONES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function fmtWait(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function fmtTime(sec: number): string {
  if (!Number.isFinite(sec)) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

export default function UploadVideo() {
  const [zones, setZones] = useState<Zone[]>(() => loadUploadVideoZones());
  const [frame, setFrame] = useState<Frame>({ width: DEFAULT_FRAME_W, height: DEFAULT_FRAME_H, url: null });
  const [draft, setDraft] = useState<Point[]>([]);
  const [name, setName] = useState('');
  const [naming, setNaming] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawMode, setDrawMode] = useState(true);
  const [mediaPlaying, setMediaPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');

  const inputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const heatCanvasRef = useRef<HTMLCanvasElement>(null);
  const draftRef = useRef(draft);
  draftRef.current = draft;

  const live = useLiveData(zones, frame, videoRef, heatCanvasRef, { initialRunning: false });

  useEffect(() => {
    localStorage.setItem(UPLOAD_VIDEO_ZONES_KEY, JSON.stringify(zones));
  }, [zones]);

  const addPoint = (point: Point) => setDraft((previous) => [...previous, point]);
  const canClose = draft.length >= 3;

  const openNaming = () => {
    if (draftRef.current.length >= 3) setNaming(true);
  };

  const cancelDraft = () => {
    setDraft([]);
    setNaming(false);
    setName('');
  };

  const confirmZone = () => {
    if (draft.length < 3) return;
    const used = zones.map((zone) => zone.color);
    const color = PALETTE.find((item) => !used.includes(item)) || PALETTE[zones.length % PALETTE.length];
    const zone: Zone = {
      id: `upload-${Date.now().toString().slice(-6)}`,
      name: name.trim() || `Video Zone ${zones.length + 1}`,
      color,
      points: draft,
      warnAt: 4,
      congestAt: 7,
      avgServiceSec: 20,
    };
    setZones([...zones, zone]);
    setSelectedId(zone.id);
    setDraft([]);
    setName('');
    setNaming(false);
  };

  const updateZone = (id: string, patch: Partial<Zone>) =>
    setZones(zones.map((zone) => (zone.id === id ? { ...zone, ...patch } : zone)));

  const deleteZone = (id: string) => {
    setZones(zones.filter((zone) => zone.id !== id));
    if (selectedId === id) setSelectedId(null);
  };

  const onUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    void live.reset();
    setMediaPlaying(false);
    setCurrentTime(0);

    if (file.type.startsWith('video/')) {
      const probe = document.createElement('video');
      probe.onloadedmetadata = () => {
        setFrame({ width: probe.videoWidth || DEFAULT_FRAME_W, height: probe.videoHeight || DEFAULT_FRAME_H, url, kind: 'video' });
        setDuration(probe.duration || 0);
      };
      probe.src = url;
      return;
    }

    const image = new Image();
    image.onload = () => {
      setFrame({ width: image.naturalWidth || DEFAULT_FRAME_W, height: image.naturalHeight || DEFAULT_FRAME_H, url, kind: 'image' });
      setDuration(0);
    };
    image.src = url;
  };

  const toggleMedia = async () => {
    const video = videoRef.current;
    if (!video || frame.kind !== 'video') return;
    if (video.paused) {
      await video.play();
      setMediaPlaying(true);
    } else {
      video.pause();
      setMediaPlaying(false);
    }
  };

  const seek = (value: number) => {
    const video = videoRef.current;
    if (!video || frame.kind !== 'video') return;
    video.currentTime = value;
    setCurrentTime(value);
  };

  const saveUploadVideoZones = () => {
    localStorage.setItem(UPLOAD_VIDEO_ZONES_KEY, JSON.stringify(zones));
    setSaveStatus('saved');
    setTimeout(() => setSaveStatus('idle'), 1800);
  };

  const downloadZones = () => {
    const payload = exportForProcessor(zones, frame);
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'upload-video-zones.json';
    link.click();
  };

  const metricList: ZoneMetric[] = zones.map(
    (zone) => live.metrics[zone.id] ?? { zoneId: zone.id, personCount: 0, waitSec: 0, status: 'normal' },
  );
  const totalPeople = metricList.reduce((sum, metric) => sum + metric.personCount, 0);
  const hottest = metricList.reduce(
    (a, b) => ((b.heatMean ?? 0) > (a.heatMean ?? 0) ? b : a),
    metricList[0] ?? { zoneId: '', personCount: 0, waitSec: 0, status: 'normal' as ZoneStatus },
  );
  const hint =
    draft.length === 0
      ? 'Upload a video or frame, pause on a useful moment, then draw zones for AI testing.'
      : `Drawing ${draft.length} point${draft.length > 1 ? 's' : ''}. Press Close zone when the polygon is ready.`;

  return (
    <div className="spotlight">
      <div className="spotlight__body">
        <div className="center">
          <div className="tiles">
            <Tile label="Video zones" value={String(zones.length)} delta={frame.kind ?? 'no media'} />
            <Tile label="Tracked IDs" value={String(live.tracks.length)} delta={live.processing ? 'processing' : `${live.latencyMs}ms`} color="#f7b955" />
            <Tile label="People in zones" value={String(totalPeople)} delta={`${metricList.length} active`} />
            <Tile
              label="Hottest zone"
              value={zones.find((zone) => zone.id === hottest.zoneId)?.name ?? 'None'}
              delta={`heat ${(hottest.heatMean ?? 0).toFixed(2)}`}
              color={STATUS_COLOR[hottest.status]}
            />
          </div>

          <div className="hintbar">
            <span className="hintbar__text">{hint}</span>
            <span className="hintbar__right">
              <span className="muted small">Draw mode</span>
              <button className={`drawtoggle ${drawMode ? 'drawtoggle--on' : ''}`} onClick={() => setDrawMode((value) => !value)}>
                {drawMode ? 'ON' : 'OFF'}
              </button>
            </span>
          </div>

          <div className="feed">
            {frame.kind === 'video' && frame.url && (
              <video
                ref={videoRef}
                className="feedvideo"
                src={frame.url}
                muted
                playsInline
                onPlay={() => setMediaPlaying(true)}
                onPause={() => setMediaPlaying(false)}
                onLoadedMetadata={(event) => setDuration(event.currentTarget.duration || 0)}
                onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
              />
            )}
            {frame.kind === 'image' && frame.url && <img className="feedvideo" src={frame.url} alt="Uploaded video frame" />}
            <canvas ref={heatCanvasRef} className="heatmap-layer" aria-hidden="true" />
            <CameraStage
              zones={zones}
              frame={frame}
              metrics={live.metrics}
              tracks={live.tracks}
              mode="upload"
              draft={draft}
              selectedZoneId={selectedId}
              onStageClick={drawMode && !naming ? addPoint : undefined}
              onSelectZone={setSelectedId}
            />
            <div className="ov editlabel">UPLOAD VIDEO - {frame.width} x {frame.height}{frame.kind === 'video' ? ` - ${fmtTime(currentTime)}` : ''}</div>
            <div className="ov ov-res">{live.connected ? 'AI connected' : 'AI idle'}</div>

            {naming && (
              <div className="namepop">
                <div className="namepop__card">
                  <div className="namepop__title">Name video zone</div>
                  <input
                    className="input"
                    autoFocus
                    placeholder="e.g. Queue lane"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') confirmZone();
                      else if (event.key === 'Escape') setNaming(false);
                    }}
                  />
                  <div className="namepop__actions">
                    <button className="btn" onClick={() => setNaming(false)}>Back</button>
                    <button className="btn btn--primary" onClick={confirmZone}>Add zone</button>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="upload-controls">
            <input ref={inputRef} type="file" accept="image/*,video/*" hidden onChange={onUpload} />
            <button className="btn btn--primary" onClick={() => inputRef.current?.click()}>Upload video / frame</button>
            <button className="btn" disabled={frame.kind !== 'video'} onClick={() => void toggleMedia()}>
              {mediaPlaying ? 'Pause video' : 'Play video'}
            </button>
            <button className="btn" disabled={!canClose} onClick={openNaming}>Close zone ({draft.length})</button>
            <button className="btn" disabled={!draft.length} onClick={() => setDraft((previous) => previous.slice(0, -1))}>Undo point</button>
            <button className="btn" disabled={!draft.length && !naming} onClick={cancelDraft}>Cancel draw</button>
            <button className="btn" disabled={!frame.url || !zones.length} onClick={() => live.setRunning(!live.running)}>
              {live.running ? 'Pause AI test' : 'Start AI test'}
            </button>
            <button className="btn" onClick={() => void live.reset()}>Reset AI</button>
            <label className="interval-control">
              Interval ms
              <input type="number" min={1} value={live.intervalMs} onChange={(event) => live.setIntervalMs(Number(event.target.value))} />
            </label>
          </div>

          {frame.kind === 'video' && (
            <div className="upload-scrub">
              <span>{fmtTime(currentTime)}</span>
              <input type="range" min={0} max={duration || 0} step={0.05} value={Math.min(currentTime, duration || 0)} onChange={(event) => seek(Number(event.target.value))} />
              <span>{fmtTime(duration)}</span>
            </div>
          )}

          <div className="livebar">
            <span className="livebar__pill" style={{ background: live.connected ? '#ef5b47' : '#565c65' }}>
              <span className="livebar__dot blink" />{live.connected ? 'AI ACTIVE' : 'NO AI'}
            </span>
            {live.processing && <span className="pipeline-note">YOLO to ByteTrack to heatmap</span>}
            {live.error && <span className="pipeline-error" title={live.error}>{live.error}</span>}
          </div>
        </div>

        <aside className="rail">
          <div className="rail__head">
            <span className="rail__label">VIDEO ZONES</span>
            <span className="muted small">{zones.length}</span>
          </div>
          {zones.length === 0 && (
            <div className="zempty">
              No video zones yet.<br />Upload media, pause on a useful frame, then click the stage to draw.
            </div>
          )}
          {zones.map((zone) => {
            const metric = live.metrics[zone.id];
            const status = metric?.status ?? 'normal';
            return (
              <div
                key={zone.id}
                className={`zonecard ${zone.id === selectedId ? 'zonecard--sel' : ''}`}
                onClick={() => setSelectedId(zone.id)}
              >
                <div className="zonecard__head">
                  <span className="dot" style={{ background: zone.color }} />
                  <input className="input input--flush" value={zone.name} onChange={(event) => updateZone(zone.id, { name: event.target.value })} />
                  <span className="zonecard__pts" style={{ color: STATUS_COLOR[status] }}>{metric?.personCount ?? 0}</span>
                  <button className="btn btn--icon" onClick={(event) => { event.stopPropagation(); deleteZone(zone.id); }}>Delete</button>
                </div>
                <div className="zonecard__grid">
                  <label>Warn at
                    <input type="number" className="input input--num" value={zone.warnAt} onChange={(event) => updateZone(zone.id, { warnAt: +event.target.value })} />
                  </label>
                  <label>Congest at
                    <input type="number" className="input input--num" value={zone.congestAt} onChange={(event) => updateZone(zone.id, { congestAt: +event.target.value })} />
                  </label>
                  <label>Service (s)
                    <input type="number" className="input input--num" value={zone.avgServiceSec} onChange={(event) => updateZone(zone.id, { avgServiceSec: +event.target.value })} />
                  </label>
                </div>
                <p className="upload-zone-metric">
                  {metric ? `${metric.status} - wait ${fmtWait(metric.waitSec)} - heat ${(metric.heatMean ?? 0).toFixed(2)}` : 'Waiting for AI test'}
                </p>
              </div>
            );
          })}

          <button className={`savebtn savebtn--${saveStatus}`} disabled={!zones.length} onClick={saveUploadVideoZones}>
            {saveStatus === 'saved' ? 'Saved video zones' : 'Save video zones'}
          </button>
          <button className="btn" disabled={!zones.length} onClick={downloadZones}>Export upload-video-zones.json</button>
          <p className="savehint">
            Upload video zones are isolated from Live Monitor. They are sent to ByteTrack while this tab runs the AI test.
          </p>
        </aside>
      </div>
    </div>
  );
}

function Tile({ label, value, delta, color }: { label: string; value: string; delta?: string; color?: string }) {
  return (
    <div className="tile">
      <div className="tile__label">{label}</div>
      <div className="tile__row">
        <span className="tile__value" style={color ? { color } : undefined}>{value}</span>
        {delta && <span className="tile__delta">{delta}</span>}
      </div>
    </div>
  );
}


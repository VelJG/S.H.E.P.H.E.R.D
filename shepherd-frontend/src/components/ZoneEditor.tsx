import { useEffect, useRef, useState } from 'react';
import type { Frame, Point, Zone } from '../types';
import CameraStage from './CameraStage';
import { exportForProcessor } from '../lib/storage';

const PALETTE = ['#4c9aff', '#d6a743', '#8b5cf6', '#2dd4bf', '#f472b6', '#fb923c'];

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

type Props = {
  zones: Zone[];
  setZones: (z: Zone[]) => void;
  frame: Frame;
  setFrame: (f: Frame) => void;
};

export default function ZoneEditor({ zones, setZones, frame, setFrame }: Props) {
  const [draft, setDraft] = useState<Point[]>([]);
  const [name, setName] = useState('');
  const [naming, setNaming] = useState(false); // name popup is open
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawMode, setDrawMode] = useState(true);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');

  const draftRef = useRef(draft);
  draftRef.current = draft;

  const addPoint = (p: Point) => setDraft((d) => [...d, p]);

  // Open the name popup (only makes sense once the polygon can close).
  const openNaming = () => {
    if (draftRef.current.length >= 3) setNaming(true);
  };

  const cancelDraft = () => {
    setDraft([]);
    setNaming(false);
    setName('');
  };

  // Confirm the name popup -> create the zone.
  const confirmZone = () => {
    if (draft.length < 3) {
      setNaming(false);
      return;
    }
    const used = zones.map((z) => z.color);
    const color = PALETTE.find((c) => !used.includes(c)) || PALETTE[zones.length % PALETTE.length];
    const zone: Zone = {
      id: `zone-${Date.now().toString().slice(-6)}`,
      name: name.trim() || `Zone ${zones.length + 1}`,
      color,
      points: draft,
      warnAt: 4,
      congestAt: 7,
      avgServiceSec: 20,
    };
    setZones([...zones, zone]);
    setDraft([]);
    setName('');
    setNaming(false);
    setSelectedId(zone.id);
  };

  // Keyboard shortcuts: U = undo point, S = save (open name popup), Q = cancel.
  // Ignored while typing in any input so it never clashes with name fields.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === 'u') { e.preventDefault(); setDraft((d) => d.slice(0, -1)); }
      else if (k === 'q') { e.preventDefault(); cancelDraft(); }
      else if (k === 's') { e.preventDefault(); openNaming(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const updateZone = (id: string, patch: Partial<Zone>) =>
    setZones(zones.map((z) => (z.id === id ? { ...z, ...patch } : z)));

  const deleteZone = (id: string) => {
    setZones(zones.filter((z) => z.id !== id));
    if (selectedId === id) setSelectedId(null);
  };

  const onUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const url = URL.createObjectURL(f);
    if (f.type.startsWith('video/')) {
      // read the video's native resolution -> canonical coordinate system
      const v = document.createElement('video');
      v.onloadedmetadata = () =>
        setFrame({ width: v.videoWidth, height: v.videoHeight, url, kind: 'video' });
      v.src = url;
    } else {
      const img = new Image();
      img.onload = () => setFrame({ width: img.naturalWidth, height: img.naturalHeight, url, kind: 'image' });
      img.src = url;
    }
  };

  const saveZones = async () => {
    if (zones.length === 0 || saveStatus === 'saving') return;
    setSaveStatus('saving');
    try {
      const base = (import.meta as any).env?.VITE_API_URL ?? '';
      const res = await fetch(`${base}/config/zones`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(exportForProcessor(zones, frame)),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSaveStatus('saved');
    } catch {
      setSaveStatus('error');
    }
    setTimeout(() => setSaveStatus('idle'), 2600);
  };

  const canClose = draft.length >= 3;
  const hint =
    draft.length === 0
      ? drawMode
        ? 'Click on the frame to drop polygon vertices. Need at least 3 points, then press S to name and save.'
        : 'Draw mode is off — you can upload a CCTV frame to draw on.'
      : `Drawing: ${draft.length} point${draft.length > 1 ? 's' : ''}. Press S to name & close${canClose ? '' : ' (need ≥3)'}, U to undo, Q to cancel.`;

  const SAVE_LABEL: Record<SaveStatus, string> = {
    idle: 'Save zones',
    saving: 'Saving…',
    saved: '✓ Saved',
    error: '⚠ Retry save',
  };

  return (
    <div className="spotlight">
      <div className="spotlight__body">
        <div className="center">
          {/* hint bar + draw toggle */}
          <div className="hintbar">
            <svg width="16" height="16" viewBox="0 0 16 16" style={{ flex: 'none' }}>
              <circle cx="8" cy="8" r="7" fill="none" stroke="#4c9aff" strokeWidth="1.4" />
              <circle cx="8" cy="4.6" r="1" fill="#4c9aff" />
              <rect x="7.2" y="6.6" width="1.6" height="5" rx="0.8" fill="#4c9aff" />
            </svg>
            <span className="hintbar__text">{hint}</span>
            <span className="hintbar__right">
              <span className="muted small">Draw mode</span>
              <button
                className={`drawtoggle ${drawMode ? 'drawtoggle--on' : ''}`}
                onClick={() => setDrawMode((v) => !v)}
              >
                {drawMode ? 'ON' : 'OFF'}
              </button>
            </span>
          </div>

          {/* stage */}
          <div className="feed">
            {frame.kind === 'video' && frame.url && (
              <video className="feedvideo" src={frame.url} autoPlay loop muted playsInline />
            )}
            <CameraStage
              zones={zones}
              frame={frame}
              mode="editor"
              draft={draft}
              selectedZoneId={selectedId}
              onStageClick={drawMode && !naming ? addPoint : undefined}
              onSelectZone={setSelectedId}
            />
            <div className="ov editlabel">EDIT · {frame.width} × {frame.height}{frame.kind === 'video' ? ' · video' : ''}</div>

            {/* name popup — appears when confirming a zone */}
            {naming && (
              <div className="namepop">
                <div className="namepop__card">
                  <div className="namepop__title">Name this zone</div>
                  <input
                    className="input"
                    autoFocus
                    placeholder="e.g. T-shirt booth"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') confirmZone();
                      else if (e.key === 'Escape') setNaming(false);
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

          {/* toolbar */}
          <div className="toolbar">
            <button className="btn btn--primary" disabled={!canClose} onClick={openNaming}>
              ✓ Close zone ({draft.length}) · S
            </button>
            <button className="btn" disabled={!draft.length} onClick={() => setDraft((d) => d.slice(0, -1))}>
              ↶ Undo point · U
            </button>
            <button className="btn" disabled={!draft.length && !naming} onClick={cancelDraft}>
              Cancel · Q
            </button>
            <input id="frameUpload" type="file" accept="image/*,video/*" hidden onChange={onUpload} />
            <button className="btn" onClick={() => document.getElementById('frameUpload')?.click()}>
              Upload frame / video
            </button>
            {frame.url && (
              <button className="btn" onClick={() => setFrame({ width: 1280, height: 720, url: null })}>
                Demo scene
              </button>
            )}
          </div>
        </div>

        {/* right rail */}
        <aside className="rail">
          <div className="rail__head">
            <span className="rail__label">ZONES</span>
            <span className="muted small">{zones.length}</span>
          </div>

          {zones.length === 0 && (
            <div className="zempty">
              No zones yet.<br />Click on the frame to drop points, then press <b>S</b> to name &amp; save an area to detect.
            </div>
          )}

          {zones.map((z) => (
            <div
              key={z.id}
              className={`zonecard ${z.id === selectedId ? 'zonecard--sel' : ''}`}
              onClick={() => setSelectedId(z.id)}
            >
              <div className="zonecard__head">
                <span className="dot" style={{ background: z.color }} />
                <input
                  className="input input--flush"
                  value={z.name}
                  onChange={(e) => updateZone(z.id, { name: e.target.value })}
                />
                <span className="zonecard__pts">{z.points.length} pts</span>
                <button className="btn btn--icon" onClick={(e) => { e.stopPropagation(); deleteZone(z.id); }}>🗑</button>
              </div>
              <div className="zonecard__grid">
                <label>Warn ≥
                  <input type="number" className="input input--num" value={z.warnAt}
                    onChange={(e) => updateZone(z.id, { warnAt: +e.target.value })} />
                </label>
                <label>Congest ≥
                  <input type="number" className="input input--num" value={z.congestAt}
                    onChange={(e) => updateZone(z.id, { congestAt: +e.target.value })} />
                </label>
                <label>Service (s)
                  <input type="number" className="input input--num" value={z.avgServiceSec}
                    onChange={(e) => updateZone(z.id, { avgServiceSec: +e.target.value })} />
                </label>
              </div>
            </div>
          ))}

          <button
            className={`savebtn savebtn--${saveStatus}`}
            disabled={zones.length === 0 || saveStatus === 'saving'}
            onClick={saveZones}
          >
            {SAVE_LABEL[saveStatus]}
          </button>
          <p className="savehint">
            {zones.length === 0
              ? 'Mark at least one zone to save.'
              : 'Saved to the backend — coordinates are stored in original image pixels (frameWidth / frameHeight) for the detection processor.'}
          </p>
        </aside>
      </div>
    </div>
  );
}

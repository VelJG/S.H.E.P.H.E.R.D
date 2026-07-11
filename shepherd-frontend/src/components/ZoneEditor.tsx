import { useRef, useState } from 'react';
import type { Frame, Point, Zone } from '../types';
import { DEFAULT_FRAME_W, DEFAULT_FRAME_H } from '../types';
import CameraStage from './CameraStage';
import { exportForProcessor } from '../lib/storage';

const PALETTE = ['#00A9E0', '#FF9900', '#22c55e', '#a855f7', '#ec4899', '#14b8a6'];

type Props = {
  zones: Zone[];
  setZones: (z: Zone[]) => void;
  frame: Frame;
  setFrame: (f: Frame) => void;
};

export default function ZoneEditor({ zones, setZones, frame, setFrame }: Props) {
  const [draft, setDraft] = useState<Point[]>([]);
  const [name, setName] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const addPoint = (p: Point) => setDraft((d) => [...d, p]);

  const finishZone = () => {
    if (draft.length < 3) return;
    const idx = zones.length;
    const zone: Zone = {
      id: `zone-${Date.now().toString().slice(-6)}`,
      name: name.trim() || `Zone ${idx + 1}`,
      color: PALETTE[idx % PALETTE.length],
      points: draft,
      warnAt: 4,
      congestAt: 7,
      avgServiceSec: 20,
    };
    setZones([...zones, zone]);
    setDraft([]);
    setName('');
    setSelectedId(zone.id);
  };

  const updateZone = (id: string, patch: Partial<Zone>) =>
    setZones(zones.map((z) => (z.id === id ? { ...z, ...patch } : z)));

  const deleteZone = (id: string) => setZones(zones.filter((z) => z.id !== id));

  const onUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const url = URL.createObjectURL(f);
    // Canonical coordinate system = the snapshot's native pixels.
    const img = new Image();
    img.onload = () => setFrame({ width: img.naturalWidth, height: img.naturalHeight, url });
    img.src = url;
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(exportForProcessor(zones, frame), null, 2)], {
      type: 'application/json',
    });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'zones.json';
    a.click();
  };

  return (
    <div className="editor">
      <div className="editor__stage">
        <div className="hint">
          {draft.length === 0
            ? 'Click on the frame to drop vertices for a monitoring zone. A zone needs at least 3 points.'
            : `Drawing: ${draft.length} points - press "Close zone" when done.`}
        </div>
        <CameraStage
          zones={zones}
          frame={frame}
          mode="editor"
          draft={draft}
          selectedZoneId={selectedId}
          onStageClick={addPoint}
        />
        <div className="toolbar">
          <input
            className="input"
            placeholder="Zone name (e.g. T-shirt booth)"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <button className="btn btn--primary" disabled={draft.length < 3} onClick={finishZone}>
            Close zone ({draft.length})
          </button>
          <button className="btn" disabled={!draft.length} onClick={() => setDraft((d) => d.slice(0, -1))}>
            Undo point
          </button>
          <button className="btn" disabled={!draft.length} onClick={() => setDraft([])}>
            Cancel
          </button>
        </div>
      </div>

      <aside className="editor__panel">
        <h3>Frame source</h3>
        <input ref={fileRef} type="file" accept="image/*" hidden onChange={onUpload} />
        <div className="row">
          <button className="btn" onClick={() => fileRef.current?.click()}>Upload camera frame</button>
          {frame.url && (
            <button className="btn" onClick={() => setFrame({ width: DEFAULT_FRAME_W, height: DEFAULT_FRAME_H, url: null })}>
              Use demo scene
            </button>
          )}
        </div>
        <p className="muted small">
          Canonical system: <b>{frame.width} x {frame.height}</b> px - zone points are stored in original image pixels.
        </p>

        <h3>Zones ({zones.length})</h3>
        <div className="zonelist">
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
                <button className="btn btn--icon" onClick={() => deleteZone(z.id)}>Delete</button>
              </div>
              <div className="zonecard__grid">
                <label>Warn at least
                  <input
                    type="number"
                    className="input input--num"
                    value={z.warnAt}
                    onChange={(e) => updateZone(z.id, { warnAt: +e.target.value })}
                  />
                </label>
                <label>Congest at least
                  <input
                    type="number"
                    className="input input--num"
                    value={z.congestAt}
                    onChange={(e) => updateZone(z.id, { congestAt: +e.target.value })}
                  />
                </label>
                <label>Service (s)
                  <input
                    type="number"
                    className="input input--num"
                    value={z.avgServiceSec}
                    onChange={(e) => updateZone(z.id, { avgServiceSec: +e.target.value })}
                  />
                </label>
              </div>
            </div>
          ))}
          {zones.length === 0 && <p className="muted">No zones yet. Draw one on the frame to the left.</p>}
        </div>

        <div className="row">
          <button className="btn btn--primary" onClick={exportJson}>Export zones.json</button>
        </div>
        <p className="muted small">
          Auto-saved to the browser. The JSON export includes <b>frameWidth/frameHeight</b> and points in <b>original image pixels</b> for the Python processor.
        </p>
      </aside>
    </div>
  );
}

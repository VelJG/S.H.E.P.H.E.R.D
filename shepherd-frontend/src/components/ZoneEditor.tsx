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
            ? '👆 Bấm lên khung để đặt các đỉnh của vùng cần theo dõi (queue trước quầy). Cần ≥3 điểm.'
            : `Đang vẽ: ${draft.length} điểm — bấm "Đóng vùng" khi xong.`}
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
            placeholder="Tên vùng (vd: Quầy áo thun)"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <button className="btn btn--primary" disabled={draft.length < 3} onClick={finishZone}>
            ✓ Đóng vùng ({draft.length})
          </button>
          <button className="btn" disabled={!draft.length} onClick={() => setDraft((d) => d.slice(0, -1))}>
            ↶ Undo điểm
          </button>
          <button className="btn" disabled={!draft.length} onClick={() => setDraft([])}>
            Huỷ
          </button>
        </div>
      </div>

      <aside className="editor__panel">
        <h3>Nguồn khung hình</h3>
        <input ref={fileRef} type="file" accept="image/*" hidden onChange={onUpload} />
        <div className="row">
          <button className="btn" onClick={() => fileRef.current?.click()}>📁 Tải frame camera</button>
          {frame.url && (
            <button className="btn" onClick={() => setFrame({ width: DEFAULT_FRAME_W, height: DEFAULT_FRAME_H, url: null })}>
              Dùng scene demo
            </button>
          )}
        </div>
        <p className="muted small">Hệ toạ độ gốc: <b>{frame.width}×{frame.height}</b> px — mọi điểm zone lưu theo pixel ảnh gốc.</p>

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
                <button className="btn btn--icon" onClick={() => deleteZone(z.id)}>🗑</button>
              </div>
              <div className="zonecard__grid">
                <label>Cảnh báo ≥
                  <input type="number" className="input input--num" value={z.warnAt}
                    onChange={(e) => updateZone(z.id, { warnAt: +e.target.value })} />
                </label>
                <label>Tắc nghẽn ≥
                  <input type="number" className="input input--num" value={z.congestAt}
                    onChange={(e) => updateZone(z.id, { congestAt: +e.target.value })} />
                </label>
                <label>Phục vụ (s)
                  <input type="number" className="input input--num" value={z.avgServiceSec}
                    onChange={(e) => updateZone(z.id, { avgServiceSec: +e.target.value })} />
                </label>
              </div>
            </div>
          ))}
          {zones.length === 0 && <p className="muted">Chưa có vùng nào. Vẽ trên khung bên trái.</p>}
        </div>

        <div className="row">
          <button className="btn btn--primary" onClick={exportJson}>⬇ Export zones.json</button>
        </div>
        <p className="muted small">
          Đã tự lưu vào trình duyệt. JSON export gồm <b>frameWidth/frameHeight</b> và points theo <b>pixel ảnh gốc</b> cho processor Python.
        </p>
      </aside>
    </div>
  );
}

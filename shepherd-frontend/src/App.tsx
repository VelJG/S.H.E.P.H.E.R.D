import { useEffect, useState } from 'react';
import type { Frame, Zone } from './types';
import { DEFAULT_FRAME_W, DEFAULT_FRAME_H } from './types';
import { loadZones, saveZones } from './lib/storage';
import LiveMonitor from './components/LiveMonitor';
import ZoneEditor from './components/ZoneEditor';

type Tab = 'live' | 'zones';

export default function App() {
  const [tab, setTab] = useState<Tab>('live');
  const [zones, setZones] = useState<Zone[]>(() => loadZones());
  const [frame, setFrame] = useState<Frame>({ width: DEFAULT_FRAME_W, height: DEFAULT_FRAME_H, url: null });

  useEffect(() => {
    saveZones(zones);
  }, [zones]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand__logo">🛡️</span>
          <span className="brand__name">S.H.E.P.H.E.R.D</span>
          <span className="brand__tag">Venue Operations · AWS</span>
        </div>
        <nav className="tabs">
          <button className={`tab ${tab === 'live' ? 'tab--on' : ''}`} onClick={() => setTab('live')}>
            Live Monitor
          </button>
          <button className={`tab ${tab === 'zones' ? 'tab--on' : ''}`} onClick={() => setTab('zones')}>
            Zone Editor
          </button>
        </nav>
        <div className="topbar__right">
          <span className="pill">ap-southeast-1</span>
        </div>
      </header>

      <main className="content">
        {tab === 'live' ? (
          <LiveMonitor zones={zones} frame={frame} />
        ) : (
          <ZoneEditor zones={zones} setZones={setZones} frame={frame} setFrame={setFrame} />
        )}
      </main>
    </div>
  );
}

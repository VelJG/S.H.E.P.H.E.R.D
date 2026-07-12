import { useEffect, useState } from 'react';
import type { Frame, Zone } from './types';
import { DEFAULT_FRAME_W, DEFAULT_FRAME_H } from './types';
import { loadZones, saveZones } from './lib/storage';
import LiveMonitor from './components/LiveMonitor';
import ZoneEditor from './components/ZoneEditor';
import DemoVideo from './components/DemoVideo';

type Tab = 'live' | 'zones' | 'demo';

function useClock(): string {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return now.toLocaleTimeString('en-GB', { hour12: false });
}

export default function App() {
  const [tab, setTab] = useState<Tab>('live');
  const [zones, setZones] = useState<Zone[]>(() => loadZones());
  const [frame, setFrame] = useState<Frame>({ width: DEFAULT_FRAME_W, height: DEFAULT_FRAME_H, url: null });
  const clock = useClock();

  useEffect(() => {
    saveZones(zones);
  }, [zones]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <svg width="22" height="22" viewBox="0 0 22 22">
            <circle cx="11" cy="11" r="8.2" fill="none" stroke="#4c9aff" strokeWidth="1.6" />
            <circle cx="11" cy="11" r="2.3" fill="#4c9aff" />
            <line x1="11" y1="0.5" x2="11" y2="4" stroke="#4c9aff" strokeWidth="1.6" />
            <line x1="11" y1="18" x2="11" y2="21.5" stroke="#4c9aff" strokeWidth="1.6" />
            <line x1="0.5" y1="11" x2="4" y2="11" stroke="#4c9aff" strokeWidth="1.6" />
            <line x1="18" y1="11" x2="21.5" y2="11" stroke="#4c9aff" strokeWidth="1.6" />
          </svg>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 9 }}>
            <span className="brand__name">SHEPHERD</span>
            <span className="brand__sub">Venue Operations</span>
          </div>
        </div>

        <nav className="nav">
          <button className={`navtab ${tab === 'live' ? 'navtab--on' : ''}`} onClick={() => setTab('live')}>
            Live Monitor
          </button>
          <button className={`navtab ${tab === 'zones' ? 'navtab--on' : ''}`} onClick={() => setTab('zones')}>
            Zone Editor
          </button>
          <button className={`navtab ${tab === 'demo' ? 'navtab--on' : ''}`} onClick={() => setTab('demo')}>
            Upload Video
          </button>
        </nav>

        <div className="topbar__right">
          <span className="online"><span className="online__dot" />5/5 online</span>
          <span className="clock">{clock}</span>
          <span className="region">ap-southeast-1</span>
          <span className="avatar">OP</span>
        </div>
      </header>

      <main className="content">
        {tab === 'live' ? (
          <LiveMonitor zones={zones} frame={frame} clock={clock} />
        ) : tab === 'zones' ? (
          <ZoneEditor zones={zones} setZones={setZones} frame={frame} setFrame={setFrame} />
        ) : (
          <DemoVideo />
        )}
      </main>
    </div>
  );
}

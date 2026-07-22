# shepherd-frontend

Frontend for **S.H.E.P.H.E.R.D** — venue operations monitoring for a hackathon
gift-booth event. Standalone from `shepherd-infra` (separate folder, separate
deploy). Runs on mock/simulated tracking so it demos without a backend.

## Pages

- **Zone Editor** — draw polygon zones on a camera frame (upload your own frame
  or use the built-in top-down scene). Because YOLO + ByteTrack tracking is
  noisy, zones are defined manually: click to place vertices, close the polygon,
  name it, set warning / congestion thresholds and average service time.
  Zones auto-save to `localStorage` and export as `zones.json`
  (normalized 0–1 polygons) for the Python processor to consume.
- **Live Monitor** — Spot.ai-style dashboard: camera feed with zone overlays and
  tracked people, metric tiles, an activity chart, a per-zone status list, and an
  incident feed. When a zone stays congested for a few ticks, an incident +
  response task workflow fires. It also posts latest local zone metrics to the
  local agent ingest endpoint.
- **Agent Copilot** — asks the local operations agent natural-language questions,
  shows the answer, prediction cards, used tool chain, and latest metrics memory.

## Run

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # -> dist/  (upload to the aabw-shepherd-frontend S3 bucket + CloudFront)
```

## Local Agentic AI wiring

Start the local agent first:

```powershell
cd ..\services\agent
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8100
```

Frontend defaults to `VITE_AGENT_URL=http://localhost:8100`. If needed, create
`shepherd-frontend/.env`:

```text
VITE_AGENT_URL=http://localhost:8100
VITE_AGENT_INGEST_URL=http://localhost:8100/agent/ingest/metrics
```

Then open the **Agent Copilot** tab and ask: `Booth nào sẽ tắc trong 2 phút tới?`.

## Wiring to the real backend later

Replace the simulated data in `src/lib/useSimulation.ts` with polling of the
API Gateway endpoints (`GET /metrics/latest`, `GET /incidents`, `PATCH …`).
The zone definitions from the editor feed the Python stream processor, which is
the real source of `personCount` per zone.

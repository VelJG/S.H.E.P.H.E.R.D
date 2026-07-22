# SHEPHERD Local Operations Agent

This folder is the local-first Agentic AI service for the SHEPHERD demo.

Current implemented layer:

- Seed demo data in `demo_data/*.json`.
- Runtime local metric history in `runtime_data/metrics.jsonl`.
- Pydantic schemas for zones, metrics, incidents, predictions, and chat responses.
- `LocalDataStore` that reads seed data, merges runtime metrics, and exposes latest metrics/incidents.
- Deterministic congestion prediction that works without a model/API key.
- FastAPI routes for health, chat, report, and live metric ingest.
- Pytest coverage for datastore, prediction, and API routes.

## Quick local check

From the repo root:

```powershell
cd services\agent
.\check-local.ps1 -Install
```

After dependencies are installed once, use:

```powershell
cd services\agent
.\check-local.ps1
```

The script runs tests and prints a datastore smoke summary.

## Start the local agent API

```powershell
cd services\agent
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8100
```

Smoke test:

```powershell
Invoke-RestMethod http://localhost:8100/agent/health
Invoke-RestMethod http://localhost:8100/agent/chat -Method Post -ContentType 'application/json' -Body '{"message":"Booth nào sẽ tắc trong 2 phút tới?"}'
```

Main local endpoints:

```text
GET  /agent/health
POST /agent/chat
GET  /agent/report
POST /agent/ingest/metrics
```

## Data layout

```text
services/agent/demo_data/zones.json       # tracked zone config seed
services/agent/demo_data/metrics.json     # tracked metric history seed
services/agent/demo_data/incidents.json   # tracked incident seed
services/agent/runtime_data/metrics.jsonl # local live metrics, ignored by git
```

`runtime_data/metrics.jsonl` is intentionally not committed. The frontend/processor ingest API will append live local metrics there in the next step.

## Append a local metric manually

```powershell
cd services\agent
$code = @"
from pathlib import Path
from app.data_store import LocalDataStore

store = LocalDataStore(Path('demo_data'))
store.append_metrics([{
    'zoneId': 'booth-2',
    'timestamp': '2026-07-22T14:02:00+07:00',
    'personCount': 8,
    'queueLength': 8,
    'waitSec': 140,
    'status': 'congested',
    'source': 'manual-local',
}])
print(store.get_latest_metrics())
"@
$code | .\.venv\Scripts\python.exe -
```

## Next implementation step

Wire the frontend Agent Copilot tab to `VITE_AGENT_URL=http://localhost:8100`, and optionally send live processor zone metrics to `POST /agent/ingest/metrics`.

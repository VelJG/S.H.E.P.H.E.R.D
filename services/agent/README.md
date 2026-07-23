# SHEPHERD Local Operations Agent

This folder is the local-first Agentic AI service for the SHEPHERD demo.

Current implemented layer:

- Seed demo data in `demo_data/*.json`.
- Runtime local metric history in `runtime_data/metrics.jsonl`.
- Pydantic schemas for zones, metrics, incidents, predictions, and chat responses.
- `LocalDataStore` that reads seed data, merges runtime metrics, and exposes latest metrics/incidents.
- Deterministic congestion prediction that works without a model/API key.
- `ShepherdAgent` tool-routing layer that chooses operational tools and returns a visible `usedTools` chain.
- Optional OpenAI LLM synthesis for real AI answers when `OPENAI_API_KEY` is set.
- Autonomous `AgentMonitor` that checks congestion risk and writes proactive alerts.
- FastAPI routes for health, chat, report, live metric ingest, monitor run, and alerts.
- Pytest coverage for datastore, prediction, agent routing, autonomous monitor, and API routes.

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

## Enable real AI answers

Create `services/agent/.env` from `.env.example` and set:

```env
AGENT_AI_ENABLED=true
AGENT_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4.1-mini
```

Behavior:

```text
operator question -> ShepherdAgent chooses tools -> tool JSON -> OpenAI rewrites/reasons -> answer
```

If the key is missing or the model call fails, the deterministic fallback still answers so the demo survives.

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

Agent tool flow:

```text
natural-language question -> ShepherdAgent -> selected tools -> operational answer + usedTools trace
```

Autonomous monitor env:

```text
AGENT_AI_ENABLED=true
AGENT_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4.1-mini
AGENT_MONITOR_ENABLED=true
AGENT_MONITOR_INTERVAL_SECONDS=5
```

The monitor also runs immediately after metric ingest, so live tracking can create alerts without waiting for the next interval.

Main local endpoints:

```text
GET  /agent/health
POST /agent/chat
GET  /agent/report
POST /agent/ingest/metrics
GET  /agent/alerts
POST /agent/monitor/run
```

## Data layout

```text
services/agent/demo_data/zones.json       # tracked zone config seed
services/agent/demo_data/metrics.json     # tracked metric history seed
services/agent/demo_data/incidents.json   # tracked incident seed
services/agent/runtime_data/metrics.jsonl       # local live metrics, ignored by git
services/agent/runtime_data/agent_alerts.jsonl  # proactive agent alerts, ignored by git
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

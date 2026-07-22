# Agent Implementation Progress

Last updated: 2026-07-22 21:29:31 +0700

Current status:
- [x] Task 2 updated: seeded fallback plus live local ingest requirement added.
- [x] Task 1 verification: venv install completed; import smoke passed.
- [x] Plan copied to repo root for teammate agents.
- [x] Task 1 scaffold complete.
- [x] Dependency smoke verified (`fastapi`, `pydantic`, `strands`).

---
# SHEPHERD Operations Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a locally runnable Agentic AI layer for SHEPHERD that predicts congestion, answers dispatcher questions, and generates shift reports.

**Architecture:** For presentation reliability, run locally: React frontend -> local FastAPI agent service -> Strands-style agent -> OpenAI model -> deterministic tools over demo venue data. Production story: CloudFront/API Gateway/Lambda -> Amazon Bedrock AgentCore Runtime -> Strands agent -> Bedrock model -> DynamoDB/S3/SNS tools.

**Tech Stack:** Python 3.11+, FastAPI, pytest, Strands Agents SDK, OpenAI provider locally, Bedrock/AgentCore provider later, React/Vite.

**Verified references:**
- Strands OpenAI provider: https://strandsagents.com/docs/user-guide/concepts/model-providers/openai/
- Strands Bedrock provider: https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/
- AgentCore Runtime: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html
- Strands to AgentCore deployment: https://strandsagents.com/docs/user-guide/deploy/deploy_to_bedrock_agentcore/

---

## Demo Contract

### Capabilities

1. **Predictive Agent**
   - Reads recent `personCount`, `queueLength`, `waitSec`, `timestamp`, and zone thresholds.
   - Estimates time to congestion.
   - Recommends staffing/redirect action.
   - Example: “Booth 2 is growing faster than service rate; congestion likely in ~90s. Send 1 staff member.”

2. **Operator Copilot**
   - Answers natural-language dashboard questions:
     - “Booth nào đông nhất?”
     - “Tóm tắt 10 phút qua.”
     - “Booth 2 tắc bao lâu rồi?”
     - “Nên gửi staff đi đâu?”

3. **Shift-report Agent**
   - Summarizes peak time, busiest zone, total incidents, average wait, longest congestion, and next-event recommendation.

### Local API

`POST http://localhost:8100/agent/chat`

```json
{
  "message": "Booth nào sẽ tắc trong 2 phút tới?",
  "sessionId": "demo-dispatcher",
  "mode": "auto"
}
```

Response:

```json
{
  "answer": "Booth 2 is highest risk. It may hit congestion in ~90s. Recommendation: send 1 staff member.",
  "intent": "prediction",
  "usedTools": ["get_metric_history", "predict_congestion", "recommend_staff_action"],
  "predictions": [
    {
      "zoneId": "booth-2",
      "zoneName": "Booth 2",
      "risk": "high",
      "etaSeconds": 90,
      "reason": "personCount slope is above service capacity",
      "recommendation": "Send 1 staff member to Booth 2."
    }
  ]
}
```


### Local live ingest contract

The agent must support both stable seeded data and live local data from the running demo.

`POST http://localhost:8100/agent/ingest/metrics`

Request accepts either a single metric, an array, or `{ "metrics": [...] }`:

```json
{
  "metrics": [
    {
      "zoneId": "booth-2",
      "timestamp": "2026-07-22T14:02:00+07:00",
      "personCount": 6,
      "queueLength": 6,
      "waitSec": 112,
      "status": "warning",
      "source": "local-frontend"
    }
  ]
}
```

Response:

```json
{ "ok": true, "count": 1 }
```

Storage:

```text
services/agent/runtime_data/metrics.jsonl
```

Data priority:

```text
runtime_data/metrics.jsonl if present
+ demo_data/metrics.json as fallback/seed
```

Demo reliability rule:

```text
If live ingest is empty or broken, prediction still works from seeded demo_data.
```

---

## Files

Create:

- `services/agent/requirements.txt`
- `services/agent/.env.example`
- `services/agent/app/__init__.py`
- `services/agent/app/main.py`
- `services/agent/app/schemas.py`
- `services/agent/app/data_store.py`
- `services/agent/app/prediction.py`
- `services/agent/app/tools.py`
- `services/agent/app/agent.py`
- `services/agent/demo_data/zones.json`
- `services/agent/demo_data/metrics.json`
- `services/agent/demo_data/incidents.json`
- `services/agent/runtime_data/metrics.jsonl` — runtime local metric history written by `/agent/ingest/metrics`; ignored by git except `.gitkeep`.
- `services/agent/tests/test_data_store.py`
- `services/agent/tests/test_prediction.py`
- `services/agent/tests/test_agent.py`
- `services/agent/tests/test_api.py`
- `services/agent/README.md`
- `shepherd-frontend/src/lib/agentClient.ts`
- `shepherd-frontend/src/components/AgentCopilot.tsx`
- `docs/agentic-ai-demo-runbook.md`

Modify:

- `shepherd-frontend/src/App.tsx`
- `shepherd-frontend/src/index.css`
- `.env.example`
- `README.md`

Do **not** add AWS CDK/AgentCore deployment in the first pass. Local demo first.

---

## Task 1: Scaffold agent service

**Progress:** Complete on 2026-07-22 21:03:41 +07:00. Files created and dependency smoke passed.

- [x] Create `services/agent/requirements.txt`:

```txt
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
pytest==8.3.4
httpx==0.28.1
python-dotenv==1.0.1
strands-agents
strands-agents-tools
openai>=1.0.0
```

- [x] Create `services/agent/.env.example`:

```env
AGENT_PROVIDER=openai
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
AGENT_DATA_DIR=./demo_data
AGENT_PORT=8100
AGENT_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

- [x] Create empty package files:

```text
services/agent/app/__init__.py
services/agent/tests/__init__.py
```

- [x] Install:

```powershell
cd "D:\Study\Hackathons\AABWHack\S.H.E.P.H.E.R.D\services\agent"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

- [ ] Commit:

```powershell
git add services/agent
git commit -m "feat: scaffold local operations agent"
```

---

## Task 2: Add seeded demo data and local live ingest

- [ ] Create `services/agent/demo_data/zones.json` with 3 zones:
  - `booth-1`, warn `4`, congest `7`
  - `booth-2`, warn `4`, congest `7`
  - `entrance`, warn `8`, congest `12`

- [ ] Create `services/agent/demo_data/metrics.json` with a clear trend:
  - `booth-2` grows from `4 -> 5 -> 6` over 3 minutes.
  - `booth-1` grows slowly.
  - `entrance` is busy but stable.

- [ ] Create `services/agent/demo_data/incidents.json`:
  - one open incident on `booth-2`
  - one resolved incident on `entrance`

- [ ] Create `services/agent/runtime_data/.gitkeep` so runtime local metric history has a stable folder. Do not commit `metrics.jsonl`.

- [ ] Update `.gitignore` for agent runtime data:

```gitignore
services/agent/.venv/
services/agent/runtime_data/*.jsonl
!services/agent/runtime_data/.gitkeep
```

- [ ] Validate:

```powershell
python -m json.tool services\agent\demo_data\zones.json > $null
python -m json.tool services\agent\demo_data\metrics.json > $null
python -m json.tool services\agent\demo_data\incidents.json > $null
```

- [ ] Commit:

```powershell
git add services/agent/demo_data
git commit -m "test: seed operations agent demo data"
```

---

## Task 3: Data models and local data store

- [ ] Create `services/agent/app/schemas.py` with Pydantic models:
  - `Zone`
  - `Metric`
  - `Incident`
  - `Prediction`
  - `AgentChatRequest`
  - `AgentChatResponse`

- [ ] Create `services/agent/app/data_store.py` with `LocalDataStore`:
  - `get_zones()`
  - `get_metric_history(zone_id=None, minutes=10)`
  - `get_latest_metrics()`
  - `list_open_incidents()`
  - `list_incidents()`

- [ ] Create `services/agent/tests/test_data_store.py`:
  - latest metrics returns one item per zone
  - booth-2 history returns 3 points
  - open incidents returns only `inc-001`

- [ ] Verify:

```powershell
cd services\agent
pytest tests/test_data_store.py -v
```

- [ ] Commit:

```powershell
git add services/agent/app/schemas.py services/agent/app/data_store.py services/agent/tests/test_data_store.py
git commit -m "feat: add local operations data store"
```

---

## Task 4: Prediction engine

- [ ] Create `services/agent/app/prediction.py`.

Functions:

```python
def predict_zone(zone, history): ...
def predict_all_zones(zones, history): ...
```

Logic:

```text
slope = (last.personCount - first.personCount) / elapsed_seconds
remaining = zone.congestAt - latest.personCount
etaSeconds = remaining / slope when slope > 0
risk = high if latest >= congestAt or etaSeconds <= 120
risk = medium if latest >= warnAt or slope > 0
risk = low otherwise
```

- [ ] Create `services/agent/tests/test_prediction.py`:
  - booth-2 is high risk
  - booth-2 ETA is <= 120s
  - booth-1 is lower risk than booth-2

- [ ] Verify:

```powershell
pytest tests/test_prediction.py tests/test_data_store.py -v
```

- [ ] Commit:

```powershell
git add services/agent/app/prediction.py services/agent/tests/test_prediction.py
git commit -m "feat: add congestion prediction engine"
```

---

## Task 5: Agent tools and deterministic fallback

- [ ] Create `services/agent/app/tools.py`.

Tools:

```python
get_latest_metrics()
get_metric_history(minutes=10)
list_open_incidents()
predict_congestion()
recommend_staff_action()
generate_shift_report()
```

- [ ] Create `services/agent/app/agent.py`.

Class:

```python
class ShepherdAgent:
    def chat(self, message: str, mode: str = "auto") -> AgentChatResponse:
        ...
```

Intent routing:

```text
prediction: contains "predict", "dự đoán", "tắc", "2 phút", "ngưỡng"
report: contains "report", "tổng kết", "ca", "shift"
copilot: default
```

Important: deterministic response must work without `OPENAI_API_KEY`.

- [ ] Create `services/agent/tests/test_agent.py`:
  - prediction question uses `predict_congestion`
  - report question uses `generate_shift_report`
  - copilot question returns busiest zone

- [ ] Verify:

```powershell
pytest tests/test_agent.py -v
```

- [ ] Commit:

```powershell
git add services/agent/app/tools.py services/agent/app/agent.py services/agent/tests/test_agent.py
git commit -m "feat: add operations agent tools"
```

---

## Task 6: FastAPI agent API

- [ ] Create `services/agent/app/main.py`.

Routes:

```text
GET  /agent/health
POST /agent/chat
GET  /agent/report
```

- [ ] Add CORS for:

```text
http://localhost:5173
http://127.0.0.1:5173
```

- [ ] Create `services/agent/tests/test_api.py`:
  - health returns ok
  - chat prediction returns prediction intent and predictions

- [ ] Verify:

```powershell
pytest tests -v
uvicorn app.main:app --host 0.0.0.0 --port 8100
```

Smoke:

```powershell
Invoke-RestMethod http://localhost:8100/agent/health
Invoke-RestMethod http://localhost:8100/agent/chat -Method Post -ContentType 'application/json' -Body '{"message":"Booth nào sẽ tắc trong 2 phút tới?"}'
```

- [ ] Commit:

```powershell
git add services/agent/app/main.py services/agent/tests/test_api.py
git commit -m "feat: expose local operations agent api"
```


---

## Task 6b: Local live metric ingest API

This task connects the live local demo to the agent memory while preserving seeded fallback data.

- [ ] Modify `services/agent/app/data_store.py`:
  - create `append_metrics(metrics: list[Metric]) -> int`
  - write each metric as one JSON line to `services/agent/runtime_data/metrics.jsonl`
  - update `get_metric_history()` to read seeded `demo_data/metrics.json` plus runtime JSONL
  - sort combined metrics by timestamp

- [ ] Modify `services/agent/app/main.py`:
  - add `POST /agent/ingest/metrics`
  - accept single metric, array, or `{ "metrics": [...] }`
  - return `{ "ok": true, "count": written }`

- [ ] Add tests in `services/agent/tests/test_ingest.py`:
  - ingest single metric
  - ingest `{ metrics: [...] }`
  - history includes runtime metric plus seeded metrics

- [ ] Optional frontend integration:
  - add `VITE_AGENT_INGEST_URL=http://localhost:8100/agent/ingest/metrics`
  - after local tracking metrics update, POST zone metrics to agent ingest
  - failures must be non-blocking; UI/AI must keep running

- [ ] Verify:

```powershell
cd services\agent
.\.venv\Scripts\Activate.ps1
pytest tests -v
uvicorn app.main:app --host 0.0.0.0 --port 8100
```

Smoke:

```powershell
Invoke-RestMethod http://localhost:8100/agent/ingest/metrics -Method Post -ContentType 'application/json' -Body '{"zoneId":"booth-2","timestamp":"2026-07-22T14:02:00+07:00","personCount":8,"queueLength":8,"waitSec":140,"status":"congested"}'
Invoke-RestMethod http://localhost:8100/agent/chat -Method Post -ContentType 'application/json' -Body '{"message":"Booth nào đang tắc?"}'
```

Expected: answer reflects the ingested high `booth-2` count.

- [ ] Commit:

```powershell
git add services/agent AGENT_IMPLEMENTATION_PLAN.md docs/superpowers/plans/2026-07-22-shepherd-operations-agent.md .gitignore
git commit -m "feat: add local agent metric ingest"
```

---

## Task 7: Optional Strands/OpenAI model rewrite

- [ ] Keep deterministic fallback as the demo-safe path.
- [ ] Add guarded Strands imports:

```python
try:
    from strands import Agent
    from strands.models.openai import OpenAIModel
except Exception:
    Agent = None
    OpenAIModel = None
```

- [ ] If `OPENAI_API_KEY` exists, let the LLM rewrite the deterministic answer using tool evidence.
- [ ] If imports/key/API fail, return deterministic fallback.
- [ ] Verify without API key:

```powershell
Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
pytest tests -v
```

- [ ] Manual verify with API key:

```powershell
$env:OPENAI_API_KEY="<local key>"
uvicorn app.main:app --host 0.0.0.0 --port 8100
```

- [ ] Commit:

```powershell
git add services/agent/app/agent.py services/agent/tests/test_agent.py
git commit -m "feat: add optional strands openai agent rewrite"
```

---

## Task 8: Frontend Agent Copilot tab

- [ ] Create `shepherd-frontend/src/lib/agentClient.ts`.

Exports:

```ts
askAgent(message: string): Promise<AgentResponse>
```

Default URL:

```text
VITE_AGENT_URL || http://localhost:8100
```

- [ ] Create `shepherd-frontend/src/components/AgentCopilot.tsx`.

UI:
  - Hero: “Agentic AI Operations Copilot”
  - Quick buttons:
    - `Booth nào đông nhất?`
    - `Booth nào sẽ tắc trong 2 phút tới?`
    - `Tóm tắt 10 phút qua`
    - `Tạo shift report`
  - Answer panel
  - Used tools chain
  - Prediction cards

- [ ] Modify `shepherd-frontend/src/App.tsx`.

Add tab:

```text
Agent Copilot
```

- [ ] Modify `shepherd-frontend/src/index.css`.

Add styles:

```text
.agent-page
.agent-main
.agent-chat
.agent-answer
.agent-tools
.agent-pred
.agent-pred--high
.agent-pred--medium
.agent-pred--low
```

- [ ] Verify:

```powershell
cd shepherd-frontend
$env:VITE_AGENT_URL="http://localhost:8100"
npm run build
```

- [ ] Commit:

```powershell
git add shepherd-frontend/src/lib/agentClient.ts shepherd-frontend/src/components/AgentCopilot.tsx shepherd-frontend/src/App.tsx shepherd-frontend/src/index.css
git commit -m "feat: add agent copilot dashboard tab"
```

---

## Task 9: Demo runbook

- [ ] Create `docs/agentic-ai-demo-runbook.md`.

Content:

```md
# SHEPHERD Agentic AI Demo Runbook

## Terminal 1: Agent

cd services/agent
.\.venv\Scripts\Activate.ps1
$env:OPENAI_API_KEY="<local only>"
uvicorn app.main:app --host 0.0.0.0 --port 8100

## Terminal 2: Frontend

cd shepherd-frontend
$env:VITE_AGENT_URL="http://localhost:8100"
npm run dev

## Ask live

- Booth nào đông nhất?
- Booth nào sẽ tắc trong 2 phút tới?
- Tóm tắt 10 phút qua
- Tạo shift report

## Pitch

For reliability, this presentation runs the Strands agent locally.
In production, the same agent is hosted on Amazon Bedrock AgentCore Runtime and switches from OpenAI to Bedrock.
```

- [ ] Modify `README.md` with a short “Agentic AI local demo” section.
- [ ] Commit:

```powershell
git add docs/agentic-ai-demo-runbook.md README.md
git commit -m "docs: add agentic ai demo runbook"
```

---

## Task 10: Full verification

- [ ] Run backend tests:

```powershell
cd services\agent
.\.venv\Scripts\Activate.ps1
pytest tests -v
```

- [ ] Run agent:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8100
```

- [ ] Run frontend:

```powershell
cd shepherd-frontend
$env:VITE_AGENT_URL="http://localhost:8100"
npm run dev
```

- [ ] Manual demo:
  - Open `http://localhost:5173`
  - Click `Agent Copilot`
  - Ask all four live questions
  - Verify each answer shows tools used
  - Verify prediction card appears for Booth 2

- [ ] Final commit:

```powershell
git status -sb
git add -A
git commit -m "feat: add local agentic operations copilot"
```

---

## Production Follow-up: AgentCore/Bedrock

Do only after local demo works.

1. Add `AGENT_PROVIDER=bedrock`.
2. Add Strands `BedrockModel`.
3. Add `DynamoDbDataStore` reading:
   - `VenueMetrics`
   - `Incidents`
   - `OperationalTasks`
   - `ConfigZones`
4. Package agent for AgentCore Runtime.
5. Add `POST /agent/chat` to Lambda/API Gateway.
6. Lambda invokes AgentCore Runtime ARN.
7. Frontend uses API Gateway URL instead of local `VITE_AGENT_URL`.

Production pitch:

```text
CloudFront Dashboard
→ API Gateway
→ Lambda /agent/chat
→ Bedrock AgentCore Runtime
→ Strands Agent
→ Bedrock model
→ DynamoDB/S3/SNS tools
```

---

## Self-review

- Predictive Agent covered.
- Operator Copilot covered.
- Shift-report Agent covered.
- Local presentation reliability covered.
- OpenAI local provider covered.
- Bedrock/AgentCore production path covered.
- AWS deploy intentionally deferred.




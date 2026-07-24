# S.H.E.P.H.E.R.D.

**S.H.E.P.H.E.R.D. — Smart Human-flow Evaluation, Prediction, Hazard Detection, Response, and Dispatch** is a real-time venue operations dashboard. It detects and tracks people from live/video footage, turns detections into zone metrics, and uses an operations agent to summarize congestion, predict overcrowding, and recommend dispatch actions.

## What runs locally

For the local demo, the system is split into small services:

```text
Phone camera / uploaded video
  -> React frontend
  -> YOLO inference service on :8080
  -> ByteTrack + zone processor on :8090
  -> local operations agent on :8100
  -> dashboard overlays, alerts, and copilot answers
```

Important: the local demo does **not** need AWS Lambda, DynamoDB, S3, Kinesis, SageMaker, or AgentCore to show live tracking. Those are the AWS production equivalents in `shepherd-infra/`.

## Folder map

```text
shepherd-frontend/              React/Vite dashboard, live monitor, upload video, zone editor, agent tab
services/inference/             YOLO FastAPI service, POST /invocations
services/stream-processor/      ByteTrack + zone API, POST /track, plus optional worker script
services/agent/                 Local FastAPI operations agent, /agent/* APIs
scripts/camera-relay.py         Local relay for phone IP Webcam URLs
shepherd-infra/                 AWS CDK infrastructure and Lambda backend scaffold
samples/                        Local sample inputs, if available
```

## Prerequisites

Install these first:

- Docker Desktop
- Node.js + npm
- Python 3.10+
- Git
- Optional: NVIDIA GPU + Docker GPU support for faster YOLO

Check basics:

```powershell
docker --version
node --version
npm --version
python --version
```

## 1. Configure local environment files

From repo root:

```powershell
cd D:\Study\Hackathons\AABWHack\S.H.E.P.H.E.R.D
Copy-Item .env.example .env -ErrorAction SilentlyContinue
Copy-Item shepherd-frontend\.env.example shepherd-frontend\.env -ErrorAction SilentlyContinue
Copy-Item services\agent\.env.example services\agent\.env -ErrorAction SilentlyContinue
```

Recommended `shepherd-frontend/.env` for local demo:

```env
VITE_YOLO_TARGET=http://localhost:8080
VITE_TRACKER_TARGET=http://localhost:8090
VITE_VISION_INTERVAL_MS=300
VITE_LIVE_FRAME_WIDTH=1280
VITE_LIVE_FRAME_HEIGHT=720
VITE_AGENT_URL=http://localhost:8100
VITE_AGENT_INGEST_URL=http://localhost:8100/agent/ingest/metrics
```

Recommended `services/agent/.env`:

```env
AGENT_AI_ENABLED=true
AGENT_PROVIDER=openai
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
AGENT_DATA_DIR=./demo_data
AGENT_PORT=8100
AGENT_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
AGENT_MONITOR_ENABLED=true
AGENT_MONITOR_INTERVAL_SECONDS=5
```

Leave `OPENAI_API_KEY` empty if you only need deterministic fallback answers. Add a key only when you want real LLM synthesis locally.

## 2. Prepare YOLO model weights

The compose file mounts the model folder into the YOLO container:

```env
SHEPHERD_MODEL_DIR=./models/yolo
```

Expected default model path inside the container:

```text
/models/yolo26s.pt
```

So either place the model at:

```text
D:\Study\Hackathons\AABWHack\S.H.E.P.H.E.R.D\models\yolo\yolo26s.pt
```

or edit root `.env`:

```env
SHEPHERD_MODEL_DIR=D:\path\to\your\yolo\model\folder
MODEL_NAME=yolo26s.pt
MODEL_PATH=/models/yolo26s.pt
```

## 3. Start YOLO + ByteTrack containers

From repo root:

```powershell
cd D:\Study\Hackathons\AABWHack\S.H.E.P.H.E.R.D
docker compose up -d --build inference stream-processor
```

Health checks:

```powershell
curl http://localhost:8080/ping
curl http://localhost:8090/ping
```

Expected services:

```text
YOLO inference:       http://localhost:8080/invocations
ByteTrack processor:  http://localhost:8090/track
```

If Docker complains about GPU support, either enable GPU support in Docker Desktop or temporarily remove/comment this line in `docker-compose.yml`:

```yaml
gpus: all
```

## 4. Start the local operations agent

From another terminal:

```powershell
cd D:\Study\Hackathons\AABWHack\S.H.E.P.H.E.R.D\services\agent
```

First-time setup if `.venv` does not exist:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run tests/smoke check:

```powershell
.\check-local.ps1
```

Start the agent API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8100
```

Health check:

```powershell
curl http://localhost:8100/agent/health
```

Agent endpoints:

```text
GET  /agent/health
POST /agent/chat
GET  /agent/report
GET  /agent/alerts
POST /agent/monitor/run
POST /agent/ingest/metrics
```

## 5. Start the frontend

From another terminal:

```powershell
cd D:\Study\Hackathons\AABWHack\S.H.E.P.H.E.R.D\shepherd-frontend
npm install
npm run dev
```

Open the Vite URL, usually:

```text
http://localhost:5173
```

Dashboard tabs:

- **Live Monitor**: live camera/video tracking view
- **Zone Editor**: draw persistent browser-local zones
- **Upload Video**: upload a video/frame and test YOLO + ByteTrack
- **Agent Copilot**: ask the operations agent questions and view alerts

## 6. Optional: use phone IP Webcam

Start the IP Webcam app on Android. Use the phone URL, for example:

```text
http://10.154.66.36:8080
```

Start the relay from repo root:

```powershell
cd D:\Study\Hackathons\AABWHack\S.H.E.P.H.E.R.D
python scripts\camera-relay.py --camera-base http://10.154.66.36:8080
```

Relay URLs:

```text
http://localhost:8899/stream.mjpg
http://localhost:8899/snapshot.jpg
http://localhost:8899/health
```

Use the relay stream/snapshot in the frontend live camera controls.

## 7. How the local demo flow works

```text
1. Frontend displays the live camera or uploaded video.
2. Every VITE_VISION_INTERVAL_MS milliseconds, frontend captures the current frame.
3. Frontend sends that JPEG frame to YOLO at :8080.
4. YOLO returns person bounding boxes.
5. Frontend sends detections + drawn zones to ByteTrack at :8090.
6. ByteTrack returns stable track IDs and zone metrics.
7. Frontend draws boxes, IDs, zones, heatmap, counts, and status.
8. Frontend posts zone metrics to the local agent at :8100.
9. Agent monitor creates alerts and Agent Copilot answers operator questions.
```

Current local persistence:

```text
Zone Editor zones       -> browser localStorage key shepherd.zones.v3
Upload Video zones      -> browser localStorage key shepherd.uploadVideo.zones.v1
Agent metric history    -> services/agent/runtime_data/metrics.jsonl
Agent alerts            -> services/agent/runtime_data/agent_alerts.jsonl
```

## 8. Optional AWS backend/CDK path

The AWS infrastructure lives in `shepherd-infra/`. It represents the production architecture:

```text
Camera -> Kinesis Video Streams -> ECS Fargate -> SageMaker YOLO
Frontend -> CloudFront -> API Gateway -> Lambda -> DynamoDB/S3/SNS
Lambda -> Bedrock/AgentCore target architecture
```

Useful CDK commands:

```powershell
cd D:\Study\Hackathons\AABWHack\S.H.E.P.H.E.R.D\shepherd-infra
npm install
npx cdk synth ShepherdInfraStack
npx cdk diff ShepherdInfraStack
npx cdk deploy ShepherdInfraStack
```

If deployed, set the frontend API URL:

```env
VITE_API_URL=https://your-api-gateway-url
```

Then Lambda can handle app APIs such as metrics, incidents, zone config, uploads, and agent route scaffolds. The local demo does not require this.

## Common troubleshooting

### Frontend says `NO AI`

Check YOLO and ByteTrack:

```powershell
curl http://localhost:8080/ping
curl http://localhost:8090/ping
```

Check `shepherd-frontend/.env` has:

```env
VITE_YOLO_TARGET=http://localhost:8080
VITE_TRACKER_TARGET=http://localhost:8090
```

Restart `npm run dev` after editing `.env`.

### Camera URL changed

Restart relay with the new phone IP:

```powershell
python scripts\camera-relay.py --camera-base http://NEW_PHONE_IP:8080
```

### Agent tab says fallback / no AI

That is okay. The agent works deterministically without an OpenAI key. To enable LLM synthesis, set `OPENAI_API_KEY` in `services/agent/.env` and restart the agent server.

### Zones disappeared

Zones are stored in browser localStorage. If you switch browser, clear site data, or use another machine, they will not follow you. Use the export button or redraw zones.

### Stop everything

```powershell
docker compose down
```

Stop frontend/agent terminals with `Ctrl+C`.

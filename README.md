# S.H.E.P.H.E.R.D.

AI-Powered Real-Time Venue Operations Monitoring System.

Planned workflow:

```text
Phone Camera -> Stream Processor -> YOLO Detection -> ByteTrack + Zone Analysis -> AWS Backend -> Dashboard
```

Current hackathon focus for this branch: implement and manage only the YOLO inference flow.

The inference service does one thing:

```text
image/frame input -> person bounding boxes output
```

ByteTrack, zone analysis, queue logic, incident logic, the API backend, dashboard, and AWS infrastructure stay outside this service.

## Repo Ownership After Frontend Pull

- `shepherd-frontend/`: frontend team's dashboard and zone editor. It can run with simulated data now and later reads from backend APIs.
- `shepherd-infra/`: existing AWS/CDK backend infrastructure track.
- `services/inference/`: YOLO-only stateless inference service owned by the AI/DevOps flow.
- `services/stream-processor/`: future processor placeholder. This is where camera ingestion, YOLO calls, ByteTrack, zone analysis, and backend writes should live later.

## Current Docker YOLO Flow

Shared compose file:

```powershell
docker compose up -d --build inference
```

On this machine, use the ignored local override so Docker mounts model/cache from `D:\AI_Data`:

```powershell
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build inference
```

Health check:

```powershell
curl http://localhost:8080/ping
```

Inference test:

```powershell
python scripts/test-invoke.py --image ../../samples/images/sample.jpg
```

Put your own test image at `samples/images/sample.jpg`. Model weights, videos, credentials, `.env` files, and Terraform state are not committed.

On this machine, Docker mounts YOLO weights from:

```text
D:\AI_Data\SHEPHERD\models\yolo
```

## Local Backup Demo

If AWS or SageMaker is unavailable during the demo, run the local backup path:

```text
local Vite frontend -> local YOLO :8080 -> local ByteTrack :8090
```

Runbook:

```text
docs/local-backup-demo.md
```

The phone camera relay script is:

```powershell
python scripts/camera-relay.py --camera-base http://PHONE_IP:8080
```

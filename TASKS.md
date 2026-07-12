# S.H.E.P.H.E.R.D. Tasks

## System Boundary

Main workflow:

```text
Phone Camera
  -> Stream Processor
  -> YOLO Inference
  -> ByteTrack
  -> Zone Analysis
  -> AWS Backend
  -> Dashboard
```

Keep service ownership clear:

- `services/inference`: stateless YOLO only.
- `services/stream-processor`: video/camera input, detection loop, ByteTrack, zone analysis, backend writes.
- `shepherd-frontend`: dashboard and zone editor.
- `shepherd-infra`: AWS backend and infrastructure.

## Current Defaults

Host laptop YOLO endpoint:

```env
YOLO_INFERENCE_URL=http://<host-or-tailscale-ip>:8080/invocations
DETECT_INTERVAL_MS=33
DETECT_INTERVAL_FALLBACK_MS=50
DETECT_IN_FLIGHT_POLICY=skip
```

Timing assumptions:

- `33ms`: high-quality local target, about 30 YOLO calls/sec.
- `50ms`: fallback when browser capture, JPEG encode, HTTP upload, JSON parse, canvas draw, or Tailscale adds lag.
- `skip`: if a request is still in flight, skip the next scheduled frame instead of queueing stale frames.

## Done

- Monorepo structure aligned with existing `shepherd-frontend` and `shepherd-infra`.
- Dockerized YOLO inference service.
- `GET /ping` health endpoint.
- `POST /invocations` image multipart endpoint.
- Person-only detection using class `0`.
- Local model mounted from `D:\AI_Data\SHEPHERD\models\yolo`.
- Docker Compose local override for host machine model/cache paths.
- Tailscale usage clarified for client testing.
- Detection timing documented: `33ms` target, `50ms` fallback, `skip` in-flight policy.
- Stream processor integration worker through Phase 3:
  - reads video/camera source
  - samples by interval
  - calls YOLO `/invocations`
  - feeds detections into ByteTrack
  - runs bottom-center zone analysis
  - writes JSONL tracks/zones output
  - fetches zones from `GET /config/zones` when `BACKEND_API_URL` is set
  - posts live zone metrics to `POST /metrics` when `BACKEND_API_URL` is set
- Stream processor incident/evidence worker through Phase 5:
  - creates incidents only on `normal/warning -> congested` transitions
  - throttles repeated incidents per zone with `INCIDENT_COOLDOWN_SEC`
  - uploads evidence frames through `GET /uploads/presign` and S3 presigned PUT
  - passes `evidenceKey` to `POST /incidents`
- ByteTrack output returns both canonical `track_id` and frontend-compatible `id`.
- Backend API Lambda scaffold for demo routes:
  - `GET /config/zones`
  - `PUT /config/zones`
  - `POST /metrics`
  - `GET /metrics/latest`
  - `GET /uploads/presign`
  - `POST /incidents`
  - `GET /incidents`
  - `PATCH /incidents/{id}`
  - `GET /tasks`
  - `PATCH /tasks/{id}`
- DynamoDB `ConfigZones` table added for zone editor output.
- `PUT /config/zones` validates and stores the latest default zone config for the dashboard and stream processor.
- Local backup demo runbook added at `docs/local-backup-demo.md`.
- Reusable phone camera relay script added at `scripts/camera-relay.py`.

## Immediate Next Tasks

1. Validate integrated YOLO -> ByteTrack -> zone metrics loop with longer sample videos.
2. Confirm teammate ByteTrack/zone contract using `tracks.jsonl`.
3. Validate backend `GET /config/zones`, `POST /metrics`, `GET /uploads/presign`,
   and `POST /incidents` against the deployed API.
4. Rehearse local backup demo from `docs/local-backup-demo.md` before the final demo.
5. Keep stream-processor output shape aligned with:

```json
{
  "timestamp_sec": 1.23,
  "tracks": [
    {
      "id": 7,
      "track_id": 7,
      "class_id": 0,
      "class_name": "person",
      "confidence": 0.91,
      "bbox_xyxy": [120, 80, 260, 430]
    }
  ]
}
```

6. Wire frontend Zone Editor save action to backend `PUT /config/zones`.
7. Replace local video source with realtime camera source.
8. Tune incident thresholds/cooldown using live demo footage.

## YOLO Inference Tasks

- Keep inference stateless.
- Keep accepted input as one image/frame per request.
- Do not add ByteTrack, zone analysis, incidents, queues, or AWS writes here.
- Keep model weights out of git.
- Keep Docker endpoint stable for other services:

```text
POST /invocations
multipart/form-data field: file
```

## Stream Processor Tasks

- Own stateful processing.
- Read from:
  - local video file for testing
  - webcam index
  - later mobile camera stream or RTSP/WebRTC bridge
- Apply detection interval config.
- Call YOLO inference.
- Feed detections into ByteTrack.
- Feed tracks into zone analysis.
- Write metrics/incidents to backend.

## Stream Inference Update Task

Update `services/stream-processor` so it becomes the integration worker
between camera/video inference and the AWS backend.

Required behavior:

1. Fetch zone configuration from backend:
   - `GET /config/zones`
   - refresh periodically, e.g. `ZONE_REFRESH_SEC=10`
2. Run the inference pipeline:
   - read camera/video frames
   - call YOLO inference via `YOLO_INFERENCE_URL`, or SageMaker later
   - feed detections into ByteTrack
   - run zone analysis
3. Push live zone metrics:
   - `POST /metrics`
   - include `ts` and `zones[]`
   - each zone should include `zoneId`, `personCount`, `queueLength`,
     `waitSec`, and `status`
   - throttle with `METRICS_POST_INTERVAL_SEC`, default around 1s
4. Create incidents only on congestion transitions:
   - `POST /incidents`
   - include `zoneId`, `title`, `severity`, `summary`, `personCount`,
     `metrics`, and optional `evidenceKey`
   - avoid spam with per-zone `INCIDENT_COOLDOWN_SEC`
5. Upload evidence screenshots when creating incidents:
   - call `GET /uploads/presign?filename=...&contentType=image/jpeg`
   - upload the JPEG directly to the returned `uploadUrl`
   - pass the returned `key` as `evidenceKey` in `POST /incidents`

Suggested env vars:

```env
BACKEND_API_URL=https://...
YOLO_INFERENCE_URL=http://localhost:8080/invocations
ZONE_REFRESH_SEC=10
METRICS_POST_INTERVAL_SEC=1
INCIDENT_COOLDOWN_SEC=60
EVIDENCE_UPLOAD_ENABLED=true
```

Ownership rule:

- `services/inference`: stateless YOLO only; no backend writes.
- `services/stream-processor`: video loop, YOLO/SageMaker calls,
  ByteTrack, zone analysis, backend writes.
- `shepherd-infra/lambda`: API validation, DynamoDB/S3 persistence,
  incident/task workflow, notifications.

## ByteTrack Tasks

- Select implementation/library.
- Convert YOLO detections to tracker input.
- Maintain track state across frames.
- Emit stable `track_id`.
- Tune for detection interval:
  - default `33ms`
  - fallback `50ms`
  - possible lower rate if network or multi-camera load increases
- Decide lost-track timeout.
- Decide confidence thresholds for track creation and retention.

## Zone Analysis Tasks

- Consume frontend zone polygons.
- Decide whether zone membership uses:
  - bbox center
  - bottom-center foot point
  - intersection ratio
- Produce per-zone metrics:
  - person count
  - queue length
  - wait/dwell seconds
  - status: normal/warning/congested
- Avoid duplicating zone logic in frontend.

## Frontend Tasks

- Continue dashboard/zone editor in `shepherd-frontend`.
- Keep simulated data until backend/processor outputs are ready.
- Later replace simulation with backend polling:
  - `GET /metrics/latest`
  - `GET /incidents`
  - `PATCH /incidents/{id}`
  - `GET /tasks`
- Do not call YOLO inference directly from production dashboard path unless intentionally doing a local demo mode.

## Backend/Infra Tasks

- Continue in `shepherd-infra`.
- Zone config:
  - `PUT /config/zones` stores the latest editor polygons in DynamoDB `ConfigZones`
  - `GET /config/zones` returns the saved polygons to dashboard and stream processor
- Processor writes:
  - `POST /metrics`
  - `POST /incidents`
  - optional presigned upload for evidence images
- Dashboard reads:
  - `GET /metrics/latest`
  - `GET /incidents`
  - `GET /tasks`
- Keep raw frames out of Lambda.

## Open Questions

- Which ByteTrack package/library will be used?
- Will realtime camera input arrive as webcam, RTSP, WebRTC, or browser-uploaded frames?
- Will the stream processor temporarily support local exported JSON, or only backend `/config/zones`?
- What is the initial MVP incident rule?
- How many simultaneous cameras are expected for demo?

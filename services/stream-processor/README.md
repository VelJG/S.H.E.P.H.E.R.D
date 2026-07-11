# Stream Processor

This service owns the stateful video-processing flow:

```text
phone camera/frame input
  -> call services/inference POST /invocations
  -> ByteTrack
  -> zone analysis
  -> metrics/incidents
  -> backend writes
```

Do not place this logic inside the YOLO inference service. `services/inference` returns person boxes only.

## ByteTrack API

The current container exposes the ByteTrack + zone-analysis API:

```text
GET  /ping
POST /track
POST /reset
```

`POST /track` accepts:

```json
{
  "detections": [
    {
      "class_id": 0,
      "class_name": "person",
      "confidence": 0.91,
      "bbox_xyxy": [120, 80, 260, 430]
    }
  ],
  "zones": [
    {
      "id": "booth-1",
      "points": [[150, 300], [470, 300], [470, 690], [150, 690]],
      "warnAt": 4,
      "congestAt": 7,
      "avgServiceSec": 20
    }
  ]
}
```

Response:

```json
{
  "tracks": [
    {
      "id": 7,
      "track_id": 7,
      "bbox_xyxy": [120, 80, 260, 430],
      "confidence": 0.91,
      "class_id": 0,
      "class_name": "person"
    }
  ],
  "zones": [
    {
      "zoneId": "booth-1",
      "personCount": 1,
      "queueLength": 1,
      "waitSec": 20,
      "status": "normal"
    }
  ]
}
```

`track_id` is the canonical tracker identifier. `id` is returned as a
frontend-compatible alias for the browser demo.

## Run With Docker Compose

From the repo root:

```powershell
docker compose up -d --build inference stream-processor
```

Health checks:

```powershell
curl http://localhost:8080/ping
curl http://localhost:8090/ping
```

`TRACK_FRAME_RATE` controls ByteTrack's expected frame rate. It defaults to `30`
in `docker-compose.yml`.

## Integration Worker: Phase 1-5

`scripts/run-detection-loop.py` runs:

```text
video/camera -> YOLO /invocations -> ByteTrack -> zone metrics -> backend metrics/incidents/evidence
```

Run locally from the repo root:

```powershell
D:\AI_Data\SHEPHERD\venvs\inference\Scripts\python.exe `
  services/stream-processor/scripts/run-detection-loop.py `
  --source samples/videos/sample.mp4 `
  --yolo-url http://localhost:8080/invocations `
  --max-detections 60 `
  --output D:\AI_Data\SHEPHERD\runs\tracks.jsonl
```

Run the same worker through Docker Compose:

```powershell
docker compose -f docker-compose.yml -f docker-compose.local.yml run --rm stream-processor `
  python scripts/run-detection-loop.py `
  --source /samples/videos/sample.mp4 `
  --yolo-url http://inference:8080/invocations `
  --max-detections 60 `
  --output /runs/tracks.jsonl
```

Backend integration env vars:

```env
BACKEND_API_URL=https://...
ZONE_REFRESH_SEC=10
METRICS_POST_INTERVAL_SEC=1
INCIDENT_COOLDOWN_SEC=60
EVIDENCE_UPLOAD_ENABLED=true
ZONES_FILE=
TRACK_FRAME_RATE=30
```

If `BACKEND_API_URL` is set, the worker fetches `GET /config/zones` and posts
`POST /metrics` every `METRICS_POST_INTERVAL_SEC`. If backend zones are not
available, it uses `ZONES_FILE` or a full-frame fallback zone.

Incidents are created only when a zone transitions into `congested` status.
`INCIDENT_COOLDOWN_SEC` prevents repeated incidents for the same zone. When
`EVIDENCE_UPLOAD_ENABLED=true`, the worker calls `GET /uploads/presign`, uploads
the current JPEG frame to the returned `uploadUrl`, and passes the returned
`key` as `evidenceKey` in `POST /incidents`.

For backend tests without S3 evidence, keep incident creation enabled but pass:

```powershell
--no-evidence-upload
```

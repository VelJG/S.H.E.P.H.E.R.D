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
      "bbox_xyxy": [120, 80, 260, 430],
      "confidence": 0.91,
      "class_id": 0
    }
  ],
  "zones": [
    {
      "zoneId": "booth-1",
      "personCount": 1,
      "waitSec": 20,
      "status": "normal"
    }
  ]
}
```

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

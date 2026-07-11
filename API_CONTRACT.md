# S.H.E.P.H.E.R.D — API Contract

The seam between the three tracks. **Processor** (laptop, YOLO+ByteTrack) is the
only writer of metrics/incidents. **Dashboard** (shepherd-frontend) only reads +
updates incident/task status. Backend = thin CRUD over DynamoDB + S3, behind
API Gateway HTTP API. Dashboard **polls** every 1–2s (no WebSocket for hackathon).

Base URL = API Gateway output `ApiGatewayUrl`. All JSON. CORS `*` (already set).

DynamoDB tables (already in `shepherd-infra`):
- `VenueMetrics` — PK `zoneId`, SK `timestamp`
- `Incidents` — PK `incidentId`
- `OperationalTasks` — PK `taskId`
- Evidence screenshots → S3 `evidence` bucket

Legend: **[MVP]** = needed for the demo · [+] = nice-to-have.

---

## A. Config — zone definitions (from Zone Editor)

| Method | Route | Purpose | Store |
|---|---|---|---|
| GET | `/config/zones` **[MVP]** | Processor + dashboard fetch zone polygons | S3 `config/zones.json` |
| PUT | `/config/zones` [+] | Save editor output (else use exported `zones.json` file) | S3 `config/zones.json` |

Body / response = Zone Editor export shape:
```json
{
  "frameWidth": 1280,
  "frameHeight": 720,
  "zones": [
    { "id": "booth-1", "name": "Quầy quà 1", "warnAt": 4, "congestAt": 7,
      "avgServiceSec": 20, "points": [[150,300],[470,300],[470,690],[150,690]] }
  ]
}
```
`points` are **original-image pixels** relative to `frameWidth × frameHeight`.

## B. Ingest — Processor → Backend (writes)

| Method | Route | Purpose |
|---|---|---|
| POST | `/metrics` **[MVP]** | Push per-zone metrics for one tick (batch) → `VenueMetrics` |
| GET | `/uploads/presign` **[MVP]** | Get presigned S3 PUT url for a congestion screenshot |
| POST | `/incidents` **[MVP]** | Create incident (auto-creates 1 response task) |

```
POST /metrics
{ "ts": "2026-07-11T14:03:22Z",
  "zones": [ { "zoneId": "booth-2", "personCount": 8, "queueLength": 8,
               "waitSec": 160, "status": "congested" } ] }

GET /uploads/presign?contentType=image/jpeg
→ { "url": "https://…s3…", "key": "evidence/booth-2/1657...jpg" }
   (processor PUTs the JPEG to url, then sends key below)

POST /incidents
{ "zoneId": "booth-2", "type": "congestion", "severity": "high",
  "personCount": 8, "screenshotKey": "evidence/booth-2/1657...jpg",
  "ts": "2026-07-11T14:03:22Z" }
→ { "incidentId": "INC-1657...", "taskId": "TASK-1657..." }
```

## C. Read + act — Dashboard → Backend

| Method | Route | Purpose |
|---|---|---|
| GET | `/metrics/latest` **[MVP]** | Latest metric per zone (live tiles + zone status) |
| GET | `/metrics?zoneId=&from=&to=` [+] | History for the activity chart |
| GET | `/incidents?status=open` **[MVP]** | Incident feed |
| GET | `/incidents/{id}` [+] | Incident detail |
| PATCH | `/incidents/{id}` **[MVP]** | `{ "status": "acknowledged" \| "resolved" }` |
| GET | `/incidents/{id}/evidence` [+] | Presigned GET url for the screenshot |
| GET | `/tasks?status=` **[MVP]** | Task board |
| PATCH | `/tasks/{id}` **[MVP]** | `{ "status": "todo" \| "in_progress" \| "done", "assignee?": "" }` |
| POST | `/tasks` [+] | Manually add a task |

```
GET /metrics/latest
→ [ { "zoneId": "booth-1", "personCount": 3, "waitSec": 60, "status": "normal",  "ts": "…" },
    { "zoneId": "booth-2", "personCount": 8, "waitSec": 160, "status": "congested", "ts": "…" } ]

GET /incidents?status=open
→ [ { "incidentId": "INC-1657...", "zoneId": "booth-2", "zoneName": "Quầy quà 2",
      "personCount": 8, "status": "open", "createdAt": "…", "screenshotKey": "…" } ]
```

## D. System

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` ✅ exists | Health check (already deployed) |

---

## Minimum for the demo (7 routes)

`GET /config/zones` · `POST /metrics` · `POST /incidents` · `GET /metrics/latest`
· `GET /incidents` · `PATCH /incidents/{id}` · `GET /tasks` + `PATCH /tasks/{id}`

Implement as **one `api` Lambda** routing on `event.routeKey` (the `lambdaRole`
already has RW on all three tables + evidence bucket). Screenshots go straight
to S3 via presigned PUT, so images never pass through Lambda.

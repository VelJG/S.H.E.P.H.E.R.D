# S.H.E.P.H.E.R.D - API Contract

The seam between the tracks. **Processor** is the only writer of metrics and
incidents. **Dashboard** reads metrics/incidents/tasks and updates incident/task
status. Backend = thin CRUD over DynamoDB + S3 behind API Gateway HTTP API.
Dashboard polls every 1-2s for the hackathon demo.

Base URL = API Gateway output `ApiGatewayUrl`. All JSON. CORS `*`.

DynamoDB tables:
- `VenueMetrics` - PK `zoneId`, SK `timestamp`
- `Incidents` - PK `incidentId`
- `OperationalTasks` - PK `taskId`
- `ConfigZones` - PK `configId` (`default` for hackathon)

S3:
- Evidence screenshots -> S3 evidence bucket

Legend: **[MVP]** = needed for the demo; **[+]** = nice-to-have.

---

## A. Config - Zone Definitions

Zone definitions come from the web Zone Editor.

| Method | Route | Purpose | Store |
|---|---|---|---|
| GET | `/config/zones` **[MVP]** | Processor + dashboard fetch zone polygons | DynamoDB `ConfigZones`, item `configId=default` |
| PUT | `/config/zones` **[MVP]** | Save editor output | DynamoDB `ConfigZones`, item `configId=default` |

Body / response shape:

```json
{
  "frameWidth": 1280,
  "frameHeight": 720,
  "zones": [
    {
      "id": "booth-1",
      "name": "Booth 1 queue",
      "warnAt": 4,
      "congestAt": 7,
      "avgServiceSec": 20,
      "points": [[150, 300], [470, 300], [470, 690], [150, 690]]
    }
  ]
}
```

`points` are original-image pixels relative to `frameWidth x frameHeight`.

---

## B. Ingest - Processor Writes

| Method | Route | Purpose |
|---|---|---|
| POST | `/metrics` **[MVP]** | Push per-zone metrics for one tick -> `VenueMetrics` |
| GET | `/uploads/presign` **[MVP]** | Get presigned S3 PUT URL for a congestion screenshot |
| POST | `/incidents` **[MVP]** | Create incident and auto-create one response task |

Preferred metrics payload:

```json
{
  "ts": "2026-07-11T14:03:22Z",
  "zones": [
    {
      "zoneId": "booth-2",
      "personCount": 8,
      "queueLength": 8,
      "waitSec": 160,
      "status": "congested"
    }
  ]
}
```

Compatibility note: the Lambda also accepts a raw metric object, an array of
metric objects, or `{ "metrics": [...] }`, but `{ "ts", "zones" }` is the
preferred processor payload for the hackathon demo.

Presigned upload:

```text
GET /uploads/presign?contentType=image/jpeg&filename=booth-2.jpg
```

Response:

```json
{
  "uploadUrl": "https://...",
  "key": "incidents/uuid-booth-2.jpg",
  "bucket": "aabw-shepherd-evidence-..."
}
```

Processor uploads the screenshot directly to S3 using `uploadUrl`, then sends
the returned `key` as the incident evidence reference.

Incident payload:

```json
{
  "zoneId": "booth-2",
  "type": "congestion",
  "severity": "high",
  "personCount": 8,
  "evidenceKey": "incidents/uuid-booth-2.jpg",
  "createdAt": "2026-07-11T14:03:22Z",
  "metrics": {
    "queueLength": 8,
    "waitSec": 160,
    "status": "congested"
  }
}
```

---

## C. Read + Act - Dashboard

| Method | Route | Purpose |
|---|---|---|
| GET | `/metrics/latest` **[MVP]** | Latest metric per zone |
| GET | `/metrics/latest?zoneId=booth-2` [+] | Latest metric for one zone |
| GET | `/incidents?status=open` **[MVP]** | Incident feed |
| GET | `/incidents/{id}` [+] | Incident detail |
| PATCH | `/incidents/{id}` **[MVP]** | Update incident status |
| GET | `/tasks?status=open` **[MVP]** | Task board |
| GET | `/tasks/{id}` [+] | Task detail |
| PATCH | `/tasks/{id}` **[MVP]** | Update task status / assignee |

Example latest metrics response:

```json
{
  "items": [
    {
      "zoneId": "booth-1",
      "personCount": 3,
      "queueLength": 3,
      "waitSec": 60,
      "status": "normal",
      "timestamp": "2026-07-11T14:03:22Z"
    },
    {
      "zoneId": "booth-2",
      "personCount": 8,
      "queueLength": 8,
      "waitSec": 160,
      "status": "congested",
      "timestamp": "2026-07-11T14:03:22Z"
    }
  ],
  "count": 2
}
```

Example incident response:

```json
{
  "items": [
    {
      "incidentId": "INC-1657",
      "zoneId": "booth-2",
      "title": "Congestion detected",
      "personCount": 8,
      "status": "open",
      "createdAt": "2026-07-11T14:03:22Z",
      "evidenceKey": "incidents/uuid-booth-2.jpg"
    }
  ],
  "count": 1
}
```

Patch incident:

```json
{ "status": "acknowledged" }
```

Patch task:

```json
{ "status": "done", "assignee": "operator-1" }
```

---

## D. System

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | Health check |

---

## Minimum Demo Routes

`GET /config/zones`, `PUT /config/zones`, `POST /metrics`,
`POST /incidents`, `GET /metrics/latest`, `GET /incidents`,
`PATCH /incidents/{id}`, `GET /tasks`, `PATCH /tasks/{id}`.

Screenshots go directly to S3 via presigned PUT, so image bytes do not pass
through Lambda.

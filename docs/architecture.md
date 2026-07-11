# Architecture

## High-Level Workflow

```text
Phone Camera
  -> Stream Processor
  -> YOLO Inference Service
  -> ByteTrack + Zone Analysis
  -> AWS Backend
  -> Dashboard
```

## Current Repo Layout

```text
shepherd-frontend/        active dashboard + zone editor from frontend team
shepherd-infra/           active AWS/CDK backend infrastructure track
services/inference/       stateless YOLO person detector
services/stream-processor/ future camera + tracking + zone processor
docs/                     architecture and YOLO notes
samples/images/           local-only test images
```

## Current Scope

Only the YOLO inference service is implemented now.

```text
image/frame input -> person bounding boxes output
```

The service is stateless. It does not store frames, run tracking, analyze zones, manage queues, create incidents, publish events, or write to AWS.

## YOLO Boundary

`services/inference` is not called directly by the dashboard. The intended later flow is:

```text
stream-processor captures frame
  -> calls POST /invocations on services/inference
  -> receives person boxes
  -> runs ByteTrack + zone analysis in stream-processor
  -> writes metrics/incidents to backend
  -> shepherd-frontend reads backend APIs
```

This keeps model serving reusable for local Docker and later SageMaker.

## Realtime Timing

Video rendering and YOLO inference should run on separate clocks.

```text
video/canvas render loop: as smooth as the client can display
YOLO inference loop: DETECT_INTERVAL_MS, default 33ms on the host laptop
fallback interval: DETECT_INTERVAL_FALLBACK_MS, default 50ms
in-flight policy: skip, never queue stale frames
```

The interval must account for the full path:

```text
browser frame capture
  -> JPEG encode
  -> HTTP upload
  -> YOLO detect
  -> JSON parse
  -> canvas draw
  -> network/Tailscale
```

`33ms` is the high-quality local target. `50ms` is the stable fallback if real client/network overhead causes visible lag.

## Future Work

- Stream Processor: phone camera input, frame sampling, invocation orchestration.
- ByteTrack + Zone Analysis: object tracking and venue-specific spatial rules.
- AWS Backend: APIs, event persistence, incident workflows, authentication.
- Dashboard: continue in `shepherd-frontend/`.
- Infrastructure: continue in `shepherd-infra/`.

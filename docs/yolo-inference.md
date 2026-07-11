# YOLO Inference Plan

## Model Choices

Local Docker testing uses `yolo26s.pt` by default because it is a practical balance for the Acer Predator Helios Neo 14 2024 with RTX 4060 8GB VRAM. It should be fast enough for hackathon iteration while giving better accuracy than a nano fallback.

Later SageMaker deployment can use `yolo26m.pt` because the cloud endpoint can be sized for higher throughput and accuracy.

`yolo26n.pt` is kept only as a fallback or smoke-test option when a smaller model is useful.

## Detection Boundary

The inference service detects only class `0`, which is `person`.

It returns bounding boxes and confidence scores. It does not run ByteTrack, zone analysis, queue detection, incident logic, dashboard logic, or AWS backend logic.

## Managed YOLO Flow

Keep the YOLO pieces in this order:

```text
services/stream-processor
  reads camera/frame later
  calls services/inference POST /invocations
  receives person bbox JSON
  runs tracking/zone logic later
  writes metrics/incidents to backend later
```

`services/inference` must stay stateless:

- no frame persistence
- no ByteTrack state
- no zone polygons
- no queue or wait-time logic
- no incident creation
- no dashboard-specific DTOs
- no AWS writes

The frontend lives in `shepherd-frontend/` and should consume backend metrics/incidents, not raw YOLO detections.

## Configuration

Environment variables:

- `MODEL_NAME`: model filename/name, default `yolo26s.pt`.
- `MODEL_PATH`: optional explicit model path. If set, this takes priority over `MODEL_NAME`.
- `IMG_SIZE`: inference image size, default `640`.
- `CONF_THRES`: confidence threshold, default `0.25`.
- `DEVICE`: `auto`, `cuda`, `cpu`, or a PyTorch device string.

CUDA is used when available. Half precision is enabled only on CUDA.

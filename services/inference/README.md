# YOLO Inference Service

Stateless FastAPI service for person detection.

```text
image/frame input -> person bounding boxes output
```

This service does not include ByteTrack, zone analysis, queue logic, incident logic, dashboard logic, or AWS backend logic.

## Endpoints

- `GET /ping`
- `POST /invocations`

`/invocations` accepts `multipart/form-data` with an image file field named `file`.

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `MODEL_NAME` | `yolo26s.pt` | Used when `MODEL_PATH` is empty. |
| `MODEL_PATH` | empty | Optional local model path. Takes priority over `MODEL_NAME`. For Windows local setup, use `D:\AI_Data\SHEPHERD\models\yolo\yolo26s.pt`. |
| `IMG_SIZE` | `640` | Inference image size. |
| `CONF_THRES` | `0.25` | Confidence threshold. |
| `DEVICE` | `auto` | Uses CUDA if available, otherwise CPU. |

CUDA automatically enables half precision.

## Windows Model Location on D Drive

On this machine, model weights and Ultralytics cache are kept on D:

```text
D:\AI_Data\SHEPHERD\models\yolo            YOLO model weights
D:\AI_Data\SHEPHERD\cache\ultralytics      Ultralytics config/cache
```

The Docker Compose file mounts:

```text
D:\AI_Data\SHEPHERD\models\yolo\yolo26s.pt -> /models/yolo26s.pt
```

For other machines, keep `.env.example` generic and either set `SHEPHERD_MODEL_DIR` / `SHEPHERD_YOLO_CACHE_DIR`, or create an ignored `docker-compose.local.yml`.

## Build and Run with Docker

```powershell
cd ..\..
docker compose up -d --build inference
```

On the main local deployment machine:

```powershell
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build inference
```

Stop:

```powershell
docker compose down
```

Logs:

```powershell
docker compose logs -f inference
```

## Test

Health:

```powershell
curl http://localhost:8080/ping
```

Inference:

```powershell
python scripts/test-invoke.py --image ../../samples/images/sample.jpg
```

The test image is not committed. Add your own image at `samples/images/sample.jpg`.

## Response Shape

```json
{
  "model": "yolo26s.pt",
  "image_size": 640,
  "detections": [
    {
      "class_id": 0,
      "class_name": "person",
      "confidence": 0.87,
      "bbox_xyxy": [120, 80, 260, 430]
    }
  ],
  "latency_ms": 24.6
}
```

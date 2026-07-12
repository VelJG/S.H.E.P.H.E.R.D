import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import cv2
import requests

try:
    import boto3
except ImportError:  # keeps local HTTP-only runs usable without boto3 installed
    boto3 = None

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.processor import ByteTrackZoneProcessor  # noqa: E402


def make_default_zones(frame_width: int, frame_height: int) -> list[dict[str, Any]]:
    return [{
        "id": "full-frame",
        "name": "Full frame",
        "warnAt": 4,
        "congestAt": 7,
        "avgServiceSec": 20,
        "points": [[0, 0], [frame_width, 0], [frame_width, frame_height], [0, frame_height]],
    }]


def load_env_file(path: str) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default
    return int(raw)


def float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default
    return float(raw)


def bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def parse_args() -> argparse.Namespace:
    load_env_file(".env")

    parser = argparse.ArgumentParser(
        description="Run video/camera -> YOLO -> ByteTrack -> zone metrics, with optional backend metrics push."
    )
    parser.add_argument("--source", default=os.getenv("VIDEO_SOURCE", "samples/videos/sample.mp4"))
    parser.add_argument("--yolo-url", default=os.getenv("YOLO_INFERENCE_URL", "http://localhost:8080/invocations"))
    parser.add_argument("--sagemaker-endpoint", default=os.getenv("SAGEMAKER_ENDPOINT_NAME", ""))
    parser.add_argument("--backend-url", default=os.getenv("BACKEND_API_URL", ""))
    parser.add_argument("--zones-file", default=os.getenv("ZONES_FILE", ""))
    parser.add_argument("--zone-refresh-sec", type=float, default=float_env("ZONE_REFRESH_SEC", 10))
    parser.add_argument("--metrics-post-interval-sec", type=float, default=float_env("METRICS_POST_INTERVAL_SEC", 1))
    parser.add_argument("--incident-cooldown-sec", type=float, default=float_env("INCIDENT_COOLDOWN_SEC", 60))
    parser.add_argument("--evidence-upload", action=argparse.BooleanOptionalAction, default=bool_env("EVIDENCE_UPLOAD_ENABLED", True))
    parser.add_argument("--interval-ms", type=int, default=int_env("DETECT_INTERVAL_MS", 33))
    parser.add_argument("--fallback-ms", type=int, default=int_env("DETECT_INTERVAL_FALLBACK_MS", 50))
    parser.add_argument("--policy", default=os.getenv("DETECT_IN_FLIGHT_POLICY", "skip"), choices=["skip"])
    parser.add_argument("--track-frame-rate", type=int, default=int_env("TRACK_FRAME_RATE", 30))
    parser.add_argument("--max-detections", type=int, default=0, help="Stop after N inference calls. 0 means no limit.")
    parser.add_argument("--output", default="", help="Optional JSONL output path.")
    parser.add_argument("--jpeg-quality", type=int, default=85)
    parser.add_argument("--show", action="store_true", help="Show a local preview window with latest tracks.")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def open_capture(source: str) -> cv2.VideoCapture:
    capture_source: str | int = int(source) if source.isdigit() else source
    cap = cv2.VideoCapture(capture_source)
    if not cap.isOpened():
        raise SystemExit(f"Cannot open source: {source}")
    return cap


def encode_frame_jpeg(frame, jpeg_quality: int) -> bytes:
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
    if not ok:
        raise RuntimeError("Failed to encode frame as JPEG")
    return buffer.tobytes()


def post_frame_http(url: str, frame, jpeg_quality: int) -> tuple[dict[str, Any], float]:
    image_bytes = encode_frame_jpeg(frame, jpeg_quality)
    started_at = time.perf_counter()
    response = requests.post(
        url,
        files={"file": ("frame.jpg", image_bytes, "image/jpeg")},
        timeout=30,
    )
    response.raise_for_status()
    end_to_end_ms = (time.perf_counter() - started_at) * 1000
    return response.json(), end_to_end_ms


def make_multipart_file_body(image_bytes: bytes) -> tuple[bytes, str]:
    boundary = f"----shepherd-{uuid.uuid4().hex}"
    body = b"".join([
        f"--{boundary}\r\n".encode("utf-8"),
        b'Content-Disposition: form-data; name="file"; filename="frame.jpg"\r\n',
        b"Content-Type: image/jpeg\r\n\r\n",
        image_bytes,
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ])
    return body, f"multipart/form-data; boundary={boundary}"


def post_frame_sagemaker(endpoint_name: str, frame, jpeg_quality: int, runtime_client: Any) -> tuple[dict[str, Any], float]:
    image_bytes = encode_frame_jpeg(frame, jpeg_quality)
    body, content_type = make_multipart_file_body(image_bytes)

    started_at = time.perf_counter()
    response = runtime_client.invoke_endpoint(
        EndpointName=endpoint_name,
        Body=body,
        ContentType=content_type,
        Accept="application/json",
    )
    response_body = response["Body"].read()
    end_to_end_ms = (time.perf_counter() - started_at) * 1000
    return json.loads(response_body.decode("utf-8")), end_to_end_ms


def create_sagemaker_runtime_client(endpoint_name: str) -> Any:
    if not endpoint_name:
        return None
    if boto3 is None:
        raise RuntimeError("boto3 is required when SAGEMAKER_ENDPOINT_NAME is set")
    return boto3.client("sagemaker-runtime")


def normalize_backend_url(backend_url: str) -> str:
    return backend_url.rstrip("/")


def fetch_backend_zones(backend_url: str) -> list[dict[str, Any]]:
    response = requests.get(f"{normalize_backend_url(backend_url)}/config/zones", timeout=10)
    response.raise_for_status()
    payload = response.json()
    zones = payload.get("zones", [])
    if not isinstance(zones, list):
        raise ValueError("Backend /config/zones response must include a zones array")
    return zones


def load_file_zones(path: str) -> list[dict[str, Any]]:
    if not path:
        return []
    zone_path = Path(path)
    if not zone_path.exists():
        raise FileNotFoundError(f"Zone file not found: {zone_path}")
    payload = json.loads(zone_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("zones"), list):
        return payload["zones"]
    raise ValueError("Zone file must be a zones array or object with zones[]")


def load_zones(
    backend_url: str,
    zones_file: str,
    previous: list[dict[str, Any]],
    fallback_zones: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if backend_url:
        try:
            zones = fetch_backend_zones(backend_url)
            if zones:
                print(f"zones: loaded {len(zones)} from backend")
                return zones
            print("zones: backend returned no zones, using fallback")
        except Exception as exc:
            print(f"zones: backend fetch failed: {exc}; using fallback")

    if zones_file:
        zones = load_file_zones(zones_file)
        print(f"zones: loaded {len(zones)} from {zones_file}")
        return zones

    if previous:
        return previous

    print("zones: using default full-frame zone")
    return fallback_zones


def post_metrics(backend_url: str, zones: list[dict[str, Any]], frame_index: int) -> None:
    if not backend_url:
        return
    payload = {
        "ts": utc_now(),
        "zones": [
            {
                **zone,
                "frameId": str(frame_index),
                "source": "stream-processor",
            }
            for zone in zones
        ],
    }
    response = requests.post(f"{normalize_backend_url(backend_url)}/metrics", json=payload, timeout=10)
    response.raise_for_status()


def encode_jpeg(frame, jpeg_quality: int) -> bytes:
    return encode_frame_jpeg(frame, jpeg_quality)


def upload_evidence(
    backend_url: str,
    frame,
    zone_metric: dict[str, Any],
    frame_index: int,
    jpeg_quality: int,
) -> str | None:
    if not backend_url:
        return None

    zone_id = str(zone_metric.get("zoneId", "unknown"))
    safe_zone_id = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in zone_id)
    filename = quote(f"{safe_zone_id}-frame-{frame_index}.jpg")
    presign_url = f"{normalize_backend_url(backend_url)}/uploads/presign?filename={filename}&contentType=image/jpeg"
    presign_response = requests.get(presign_url, timeout=10)
    presign_response.raise_for_status()
    presign_payload = presign_response.json()
    upload_url = presign_payload.get("uploadUrl")
    evidence_key = presign_payload.get("key")
    if not upload_url or not evidence_key:
        raise ValueError("Presign response must include uploadUrl and key")

    image_bytes = encode_jpeg(frame, jpeg_quality)
    upload_response = requests.put(upload_url, data=image_bytes, headers={"Content-Type": "image/jpeg"}, timeout=30)
    upload_response.raise_for_status()
    return str(evidence_key)


def post_incident(
    backend_url: str,
    zone_metric: dict[str, Any],
    frame_index: int,
    evidence_key: str | None,
) -> None:
    if not backend_url:
        return

    zone_id = str(zone_metric.get("zoneId", "unknown"))
    person_count = int(zone_metric.get("personCount", 0))
    wait_sec = int(zone_metric.get("waitSec", 0))
    payload = {
        "zoneId": zone_id,
        "type": "congestion",
        "title": "Congestion detected",
        "severity": "high",
        "summary": f"Zone {zone_id} entered congested status with {person_count} people and estimated wait {wait_sec}s.",
        "personCount": person_count,
        "createdAt": utc_now(),
        "metrics": {
            "queueLength": zone_metric.get("queueLength", person_count),
            "waitSec": wait_sec,
            "status": zone_metric.get("status", "congested"),
            "frameId": str(frame_index),
        },
        "source": "stream-processor",
    }
    if evidence_key:
        payload["evidenceKey"] = evidence_key

    response = requests.post(f"{normalize_backend_url(backend_url)}/incidents", json=payload, timeout=10)
    response.raise_for_status()


def handle_incidents(
    backend_url: str,
    zone_metrics: list[dict[str, Any]],
    frame,
    frame_index: int,
    jpeg_quality: int,
    evidence_upload: bool,
    incident_cooldown_sec: float,
    previous_status: dict[str, str],
    last_incident_at: dict[str, float],
    now_monotonic: float,
) -> None:
    if not backend_url:
        for zone in zone_metrics:
            previous_status[str(zone.get("zoneId", "unknown"))] = str(zone.get("status", "normal"))
        return

    for zone_metric in zone_metrics:
        zone_id = str(zone_metric.get("zoneId", "unknown"))
        current_status = str(zone_metric.get("status", "normal"))
        old_status = previous_status.get(zone_id, "normal")
        previous_status[zone_id] = current_status

        entered_congestion = current_status == "congested" and old_status != "congested"
        cooldown_ready = now_monotonic - last_incident_at.get(zone_id, -float("inf")) >= incident_cooldown_sec
        if not entered_congestion or not cooldown_ready:
            continue

        evidence_key = None
        if evidence_upload:
            try:
                evidence_key = upload_evidence(backend_url, frame, zone_metric, frame_index, jpeg_quality)
                print(f"incident: uploaded evidence for zone={zone_id} key={evidence_key}")
            except Exception as exc:
                print(f"incident: evidence upload failed for zone={zone_id}: {exc}")

        try:
            post_incident(backend_url, zone_metric, frame_index, evidence_key)
            last_incident_at[zone_id] = now_monotonic
            print(f"incident: created zone={zone_id} evidence={evidence_key or '<none>'}")
        except Exception as exc:
            print(f"incident: post failed for zone={zone_id}: {exc}")


def draw_tracks(frame, tracks: list[dict[str, Any]]) -> None:
    for track in tracks:
        x1, y1, x2, y2 = [int(v) for v in track["bbox_xyxy"]]
        label = f"id {track['track_id']} {track['confidence']:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 80), 2)
        cv2.putText(frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 80), 2)


def is_file_source(source: str) -> bool:
    return not source.isdigit() and Path(source).exists()


def main() -> None:
    args = parse_args()
    cap = open_capture(args.source)
    file_source = is_file_source(args.source)
    processor = ByteTrackZoneProcessor(frame_rate=args.track_frame_rate)
    sagemaker_runtime_client = create_sagemaker_runtime_client(args.sagemaker_endpoint)

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    source_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    source_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
    fallback_zones = make_default_zones(source_width, source_height)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    active_interval_ms = args.interval_ms
    next_due_sec = 0.0
    started_at = time.perf_counter()
    frame_index = 0
    calls = 0
    latest_tracks: list[dict[str, Any]] = []
    zones: list[dict[str, Any]] = []
    last_zone_refresh = -float("inf")
    last_metrics_post = -float("inf")
    previous_zone_status: dict[str, str] = {}
    last_incident_at: dict[str, float] = {}

    output_file = None
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_file = output_path.open("w", encoding="utf-8")

    print(
        f"source={args.source} source_fps={source_fps:.2f} total_frames={total_frames} "
        f"yolo_url={args.yolo_url} sagemaker_endpoint={args.sagemaker_endpoint or '<disabled>'} "
        f"backend_url={args.backend_url or '<disabled>'} "
        f"interval_ms={args.interval_ms} fallback_ms={args.fallback_ms} policy={args.policy}"
    )

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            timestamp_sec = frame_index / source_fps if file_source else time.perf_counter() - started_at
            now_monotonic = time.perf_counter()

            if now_monotonic - last_zone_refresh >= args.zone_refresh_sec:
                zones = load_zones(args.backend_url, args.zones_file, zones, fallback_zones)
                last_zone_refresh = now_monotonic

            if timestamp_sec + 1e-9 < next_due_sec:
                if args.show:
                    preview = frame.copy()
                    draw_tracks(preview, latest_tracks)
                    cv2.imshow("SHEPHERD stream processor", preview)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                frame_index += 1
                continue

            if args.sagemaker_endpoint:
                yolo_response, end_to_end_ms = post_frame_sagemaker(
                    args.sagemaker_endpoint,
                    frame,
                    args.jpeg_quality,
                    sagemaker_runtime_client,
                )
            else:
                yolo_response, end_to_end_ms = post_frame_http(args.yolo_url, frame, args.jpeg_quality)
            detections = yolo_response.get("detections", [])
            yolo_latency_ms = yolo_response.get("latency_ms")
            tracked = processor.update(detections, zones)
            latest_tracks = tracked["tracks"]
            zone_metrics = tracked["zones"]

            row = {
                "frame_index": frame_index,
                "timestamp_sec": round(timestamp_sec, 3),
                "interval_ms": active_interval_ms,
                "person_count": len(detections),
                "track_count": len(latest_tracks),
                "yolo_latency_ms": yolo_latency_ms,
                "end_to_end_ms": round(end_to_end_ms, 2),
                "detections": detections,
                "tracks": latest_tracks,
                "zones": zone_metrics,
            }
            print(
                f"t={row['timestamp_sec']:>7.3f}s frame={frame_index:<7} "
                f"detections={row['person_count']:<3} tracks={row['track_count']:<3} "
                f"zones={len(zone_metrics):<2} yolo_ms={yolo_latency_ms} e2e_ms={row['end_to_end_ms']}"
            )

            if output_file:
                output_file.write(json.dumps(row, ensure_ascii=False) + "\n")
                output_file.flush()

            if args.backend_url and now_monotonic - last_metrics_post >= args.metrics_post_interval_sec:
                last_metrics_post = now_monotonic
                try:
                    post_metrics(args.backend_url, zone_metrics, frame_index)
                    print(f"metrics: posted {len(zone_metrics)} zones")
                except Exception as exc:
                    print(f"metrics: post failed: {exc}")

            handle_incidents(
                args.backend_url,
                zone_metrics,
                frame,
                frame_index,
                args.jpeg_quality,
                args.evidence_upload,
                args.incident_cooldown_sec,
                previous_zone_status,
                last_incident_at,
                now_monotonic,
            )

            if args.show:
                preview = frame.copy()
                draw_tracks(preview, latest_tracks)
                cv2.imshow("SHEPHERD stream processor", preview)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            calls += 1
            active_interval_ms = args.fallback_ms if end_to_end_ms > args.interval_ms else args.interval_ms
            next_due_sec = timestamp_sec + active_interval_ms / 1000
            frame_index += 1

            if args.max_detections and calls >= args.max_detections:
                break
    finally:
        cap.release()
        if output_file:
            output_file.close()
        if args.show:
            cv2.destroyAllWindows()

    elapsed_sec = time.perf_counter() - started_at
    print(f"done inference_calls={calls} elapsed_sec={elapsed_sec:.2f}")


if __name__ == "__main__":
    main()

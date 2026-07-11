import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

import cv2
import requests


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


def parse_args() -> argparse.Namespace:
    load_env_file(".env")

    parser = argparse.ArgumentParser(
        description="Read video/camera frames and call the stateless YOLO inference service on a timed interval."
    )
    parser.add_argument("--source", default="samples/videos/sample.mp4", help="Video path, camera index, or stream URL.")
    parser.add_argument("--url", default=os.getenv("YOLO_INFERENCE_URL", "http://localhost:8080/invocations"))
    parser.add_argument("--interval-ms", type=int, default=int_env("DETECT_INTERVAL_MS", 33))
    parser.add_argument("--fallback-ms", type=int, default=int_env("DETECT_INTERVAL_FALLBACK_MS", 50))
    parser.add_argument("--policy", default=os.getenv("DETECT_IN_FLIGHT_POLICY", "skip"), choices=["skip"])
    parser.add_argument("--max-detections", type=int, default=0, help="Stop after N inference calls. 0 means no limit.")
    parser.add_argument("--output", default="", help="Optional JSONL output path.")
    parser.add_argument("--jpeg-quality", type=int, default=85)
    parser.add_argument("--show", action="store_true", help="Show a local preview window with latest boxes.")
    return parser.parse_args()


def open_capture(source: str) -> cv2.VideoCapture:
    capture_source: str | int = int(source) if source.isdigit() else source
    cap = cv2.VideoCapture(capture_source)
    if not cap.isOpened():
        raise SystemExit(f"Cannot open source: {source}")
    return cap


def post_frame(url: str, frame, jpeg_quality: int) -> tuple[dict[str, Any], float]:
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
    if not ok:
        raise RuntimeError("Failed to encode frame as JPEG")

    started_at = time.perf_counter()
    response = requests.post(
        url,
        files={"file": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
        timeout=30,
    )
    response.raise_for_status()
    end_to_end_ms = (time.perf_counter() - started_at) * 1000
    return response.json(), end_to_end_ms


def draw_boxes(frame, detections: list[dict[str, Any]]) -> None:
    for det in detections:
        x1, y1, x2, y2 = [int(v) for v in det["bbox_xyxy"]]
        label = f"person {det['confidence']:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 80), 2)
        cv2.putText(frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 80), 2)


def is_file_source(source: str) -> bool:
    return not source.isdigit() and Path(source).exists()


def main() -> None:
    args = parse_args()
    cap = open_capture(args.source)
    file_source = is_file_source(args.source)

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    active_interval_ms = args.interval_ms
    next_due_sec = 0.0
    started_at = time.perf_counter()
    frame_index = 0
    calls = 0
    latest_detections: list[dict[str, Any]] = []

    output_file = None
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_file = output_path.open("w", encoding="utf-8")

    print(
        f"source={args.source} source_fps={source_fps:.2f} total_frames={total_frames} "
        f"url={args.url} interval_ms={args.interval_ms} fallback_ms={args.fallback_ms} policy={args.policy}"
    )

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            timestamp_sec = frame_index / source_fps if file_source else time.perf_counter() - started_at
            if timestamp_sec + 1e-9 < next_due_sec:
                if args.show:
                    preview = frame.copy()
                    draw_boxes(preview, latest_detections)
                    cv2.imshow("SHEPHERD detection loop", preview)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                frame_index += 1
                continue

            result, end_to_end_ms = post_frame(args.url, frame, args.jpeg_quality)
            latest_detections = result.get("detections", [])
            yolo_latency_ms = result.get("latency_ms")

            row = {
                "frame_index": frame_index,
                "timestamp_sec": round(timestamp_sec, 3),
                "interval_ms": active_interval_ms,
                "person_count": len(latest_detections),
                "yolo_latency_ms": yolo_latency_ms,
                "end_to_end_ms": round(end_to_end_ms, 2),
                "detections": latest_detections,
            }
            print(
                f"t={row['timestamp_sec']:>7.3f}s frame={frame_index:<7} "
                f"persons={row['person_count']:<3} yolo_ms={yolo_latency_ms} e2e_ms={row['end_to_end_ms']}"
            )

            if output_file:
                output_file.write(json.dumps(row, ensure_ascii=False) + "\n")
                output_file.flush()

            if args.show:
                preview = frame.copy()
                draw_boxes(preview, latest_detections)
                cv2.imshow("SHEPHERD detection loop", preview)
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

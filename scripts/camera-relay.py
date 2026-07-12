import argparse
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Relay an IP Webcam phone camera to local /stream.mjpg and /snapshot.jpg endpoints."
    )
    parser.add_argument("--camera-base", default=os.getenv("IP_CAMERA_BASE", "http://192.168.1.50:8080"))
    parser.add_argument("--stream-path", default=os.getenv("IP_CAMERA_STREAM_PATH", "/video"))
    parser.add_argument("--snapshot-path", default=os.getenv("IP_CAMERA_SNAPSHOT_PATH", "/shot.jpg"))
    parser.add_argument("--host", default=os.getenv("RELAY_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("RELAY_PORT", "8899")))
    parser.add_argument("--timeout-sec", type=float, default=float(os.getenv("RELAY_TIMEOUT_SEC", "10")))
    return parser.parse_args()


def make_handler(camera_base: str, stream_path: str, snapshot_path: str, timeout_sec: float):
    camera_base = camera_base.rstrip("/")

    def fetch(path: str):
        return urlopen(
            Request(f"{camera_base}{path}", headers={"User-Agent": "SHEPHERD-camera-relay"}),
            timeout=timeout_sec,
        )

    class Handler(BaseHTTPRequestHandler):
        def send_common_headers(self, content_type: str) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", content_type)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_common_headers("text/plain")
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/snapshot.jpg":
                    upstream = fetch(snapshot_path)
                    data = upstream.read()
                    self.send_response(200)
                    self.send_common_headers(upstream.headers.get("Content-Type", "image/jpeg"))
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return

                if parsed.path == "/stream.mjpg":
                    upstream = fetch(stream_path)
                    content_type = upstream.headers.get("Content-Type", "multipart/x-mixed-replace")
                    self.send_response(200)
                    self.send_common_headers(content_type)
                    self.end_headers()
                    while True:
                        chunk = upstream.read(8192)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                    return

                if parsed.path in ("/", "/health"):
                    body = b"SHEPHERD camera relay OK\n"
                    self.send_response(200)
                    self.send_common_headers("text/plain")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                self.send_response(404)
                self.end_headers()
            except Exception as exc:
                message = f"relay error: {exc}\n".encode("utf-8")
                self.send_response(502)
                self.send_common_headers("text/plain")
                self.send_header("Content-Length", str(len(message)))
                self.end_headers()
                self.wfile.write(message)

        def log_message(self, fmt: str, *args) -> None:
            print(f"{self.address_string()} - {fmt % args}")

    return Handler


def main() -> None:
    args = parse_args()
    handler = make_handler(args.camera_base, args.stream_path, args.snapshot_path, args.timeout_sec)
    print(f"Camera base: {args.camera_base.rstrip('/')}")
    print(f"Stream:      http://localhost:{args.port}/stream.mjpg -> {args.camera_base.rstrip('/')}{args.stream_path}")
    print(f"Snapshot:    http://localhost:{args.port}/snapshot.jpg -> {args.camera_base.rstrip('/')}{args.snapshot_path}")
    print(f"Health:      http://localhost:{args.port}/health")
    ThreadingHTTPServer((args.host, args.port), handler).serve_forever()


if __name__ == "__main__":
    main()

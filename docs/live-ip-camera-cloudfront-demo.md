# Live IP Camera Demo on CloudFront

This runbook explains the hackathon/demo path for showing a live phone camera feed on the deployed CloudFront frontend and running AWS AI tracking against that feed.

## Target flow

```text
Android phone running IP Webcam
  -> laptop relay server
  -> HTTPS public tunnel
  -> CloudFront frontend shows live feed
  -> frontend samples snapshots
  -> API Gateway POST /demo/infer-frame
  -> Lambda invokes SageMaker YOLO
  -> API Gateway POST /demo/track
  -> frontend draws boxes / zone metrics / AI status
```

## Why we need the laptop relay

The phone camera app usually exposes a LAN-only HTTP URL such as:

```text
http://PHONE_IP:8080/video
http://PHONE_IP:8080/shot.jpg
```

The deployed frontend is HTTPS on CloudFront. A browser should not be expected to safely load and canvas-capture a private HTTP camera URL from an HTTPS site. AWS also cannot reach a `192.168.x.x` phone address on your local Wi-Fi.

The laptop can reach the phone, so the laptop becomes the bridge:

```text
phone LAN HTTP -> laptop localhost relay -> public HTTPS tunnel -> deployed frontend
```

## What already exists in AWS

The deployed stack already has the demo AI API path:

```text
POST /demo/infer-frame  -> Lambda -> SageMaker YOLO
POST /demo/track        -> Lambda zone metric/tracking response
POST /demo/reset        -> reset endpoint for frontend demo state
```

Current API base:

```text
https://9hgrymkggl.execute-api.ap-southeast-1.amazonaws.com
```

Current CloudFront frontend:

```text
https://d2tan4td1s1urm.cloudfront.net
```

## Showtime setup checklist

### 1. Start IP Webcam on Android

1. Connect phone and laptop to the same Wi-Fi.
2. Open the IP Webcam app.
3. Start the camera server.
4. Note the phone URL shown by the app, for example:

```text
http://192.168.1.50:8080
```

5. On the laptop, test these in a browser:

```text
http://192.168.1.50:8080/video
http://192.168.1.50:8080/shot.jpg
```

If `/video` does not work, try app-displayed alternatives such as `/videofeed` or `/mjpeg`. If `/shot.jpg` does not work, use the snapshot URL displayed by the app.

### 2. Run a laptop relay server

Create a temporary file outside git, for example:

```powershell
New-Item -ItemType Directory -Force "$env:TEMP\shepherd-camera-relay" | Out-Null
notepad "$env:TEMP\shepherd-camera-relay\relay.py"
```

Paste this relay code:

```python
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

CAMERA_BASE = os.environ.get("IP_CAMERA_BASE", "http://192.168.1.50:8080").rstrip("/")
STREAM_PATH = os.environ.get("IP_CAMERA_STREAM_PATH", "/video")
SNAPSHOT_PATH = os.environ.get("IP_CAMERA_SNAPSHOT_PATH", "/shot.jpg")
PORT = int(os.environ.get("RELAY_PORT", "8899"))


def fetch(path: str):
    return urlopen(Request(f"{CAMERA_BASE}{path}", headers={"User-Agent": "SHEPHERD-relay"}), timeout=10)


class Handler(BaseHTTPRequestHandler):
    def cors(self, content_type: str):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Type", content_type)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        try:
            if self.path.startswith("/snapshot.jpg"):
                upstream = fetch(SNAPSHOT_PATH)
                data = upstream.read()
                self.send_response(200)
                self.cors("image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

            if self.path.startswith("/stream.mjpg"):
                upstream = fetch(STREAM_PATH)
                content_type = upstream.headers.get("Content-Type", "multipart/x-mixed-replace")
                self.send_response(200)
                self.cors(content_type)
                self.end_headers()
                while True:
                    chunk = upstream.read(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                return

            if self.path in ("/", "/health"):
                body = b"SHEPHERD camera relay OK\n"
                self.send_response(200)
                self.cors("text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            self.send_response(404)
            self.end_headers()
        except Exception as exc:
            message = f"relay error: {exc}\n".encode()
            self.send_response(502)
            self.cors("text/plain")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            self.wfile.write(message)


if __name__ == "__main__":
    print(f"Camera base: {CAMERA_BASE}")
    print(f"Stream:      http://localhost:{PORT}/stream.mjpg -> {CAMERA_BASE}{STREAM_PATH}")
    print(f"Snapshot:    http://localhost:{PORT}/snapshot.jpg -> {CAMERA_BASE}{SNAPSHOT_PATH}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
```

Run it:

```powershell
$env:IP_CAMERA_BASE = "http://PHONE_IP:8080"
$env:IP_CAMERA_STREAM_PATH = "/video"
$env:IP_CAMERA_SNAPSHOT_PATH = "/shot.jpg"
$env:RELAY_PORT = "8899"
python "$env:TEMP\shepherd-camera-relay\relay.py"
```

Test locally:

```powershell
Invoke-WebRequest http://localhost:8899/health
Invoke-WebRequest http://localhost:8899/snapshot.jpg -OutFile "$env:TEMP\shepherd-camera-relay\snapshot.jpg"
```

Open this in a browser:

```text
http://localhost:8899/stream.mjpg
```

### 3. Expose the laptop relay with HTTPS

Install `cloudflared`, then run:

```powershell
cloudflared tunnel --url http://localhost:8899
```

Cloudflare Quick Tunnels create a random `trycloudflare.com` URL and proxy it to the local service. Official docs: <https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/>

Example tunnel output:

```text
https://abc-random-name.trycloudflare.com
```

Your public demo URLs become:

```text
Stream URL:   https://abc-random-name.trycloudflare.com/stream.mjpg
Snapshot URL: https://abc-random-name.trycloudflare.com/snapshot.jpg
```

Keep both the relay terminal and the `cloudflared` terminal open during the demo.

### 4. Use the deployed CloudFront frontend

Open:

```text
https://d2tan4td1s1urm.cloudfront.net
```

For the current deployed upload-video demo:

1. Upload a demo video/frame.
2. Draw at least one zone and close it.
3. Click **Start AI test**.
4. The page calls AWS SageMaker through API Gateway and shows `DEMO AI` / `AI connected` after the first successful frame.

For true live camera mode, the frontend needs a live URL input mode with:

```text
Stream URL:   https://abc-random-name.trycloudflare.com/stream.mjpg
Snapshot URL: https://abc-random-name.trycloudflare.com/snapshot.jpg
```

Expected frontend behavior for live mode:

1. Show `stream.mjpg` as the live camera background.
2. Fetch `snapshot.jpg` every `VITE_VISION_INTERVAL_MS` or configured interval.
3. Send each snapshot as multipart `file` to:

```text
POST https://9hgrymkggl.execute-api.ap-southeast-1.amazonaws.com/demo/infer-frame
```

4. Send YOLO detections + zones to:

```text
POST https://9hgrymkggl.execute-api.ap-southeast-1.amazonaws.com/demo/track
```

5. Draw boxes, zone counts, wait time, and congestion status over the live feed.

## Quick verification commands

Verify AWS API health:

```powershell
Invoke-WebRequest https://9hgrymkggl.execute-api.ap-southeast-1.amazonaws.com/health
```

Verify tunnel snapshot from the laptop:

```powershell
Invoke-WebRequest https://abc-random-name.trycloudflare.com/snapshot.jpg -OutFile "$env:TEMP\camera-snapshot.jpg"
```

Verify the deployed frontend is serving the current build:

```powershell
Invoke-WebRequest https://d2tan4td1s1urm.cloudfront.net
```

## Troubleshooting

### The deployed page cannot show the stream

Check:

- Phone and laptop are on same Wi-Fi.
- `http://PHONE_IP:8080/video` opens on laptop.
- `http://localhost:8899/stream.mjpg` opens on laptop.
- `https://...trycloudflare.com/stream.mjpg` opens from another browser tab.
- The frontend uses an `<img>` element for MJPEG streams. A normal `<video>` element usually will not play MJPEG.

### AI stays `NO AI`

Check:

- At least one zone exists, or live mode has a full-frame fallback zone.
- `snapshot.jpg` URL returns a JPEG.
- Browser console/network shows 200 for `/demo/infer-frame`.
- Browser console/network shows 200 for `/demo/track`.
- SageMaker endpoint is `InService`:

```powershell
aws sagemaker describe-endpoint --endpoint-name aabw-shepherd-yolo-endpoint --query EndpointStatus --output text
```

### Tunnel URL changes

Quick Tunnel URLs are temporary and random. If you restart `cloudflared`, copy the new `https://...trycloudflare.com` URL into the frontend live camera fields again.

### Security warning

Do not leave the tunnel open after the demo. Stop `cloudflared` and the relay server when done. The public tunnel exposes your camera relay to anyone with the URL.

## Architecture note for slides

For hackathon live demo:

```text
IP Webcam -> Laptop relay/tunnel -> CloudFront FE -> API Gateway/Lambda -> SageMaker -> FE overlays
```

For production architecture:

```text
Real camera -> Kinesis Video Streams -> ECS/Fargate stream processor -> SageMaker -> API Gateway/Lambda -> DynamoDB/S3 -> CloudFront dashboard
```

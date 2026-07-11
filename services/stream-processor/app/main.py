from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.processor import ByteTrackZoneProcessor


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

processor = ByteTrackZoneProcessor(frame_rate=10)


@app.get("/ping")
def ping() -> dict[str, bool]:
    return {"ok": True}


@app.post("/track")
def track(payload: dict[str, Any]) -> dict[str, Any]:
    return processor.update(payload.get("detections", []), payload.get("zones", []))


@app.post("/reset")
def reset() -> dict[str, bool]:
    processor.reset()
    return {"ok": True}

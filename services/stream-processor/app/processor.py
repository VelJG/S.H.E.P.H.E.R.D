from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import numpy as np
from ultralytics.trackers.byte_tracker import BYTETracker

from app.zone import Point, point_in_polygon


PERSON_CLASS_ID = 0


@dataclass(frozen=True)
class Zone:
    id: str
    points: tuple[Point, ...]
    warn_at: int = 4
    congest_at: int = 7
    avg_service_sec: int = 20

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Zone":
        return cls(
            id=str(value["id"]),
            points=tuple((float(p[0]), float(p[1])) for p in value["points"]),
            warn_at=int(value.get("warnAt", value.get("warn_at", 4))),
            congest_at=int(value.get("congestAt", value.get("congest_at", 7))),
            avg_service_sec=int(value.get("avgServiceSec", value.get("avg_service_sec", 20))),
        )


class _DetectionBatch:
    """Small adapter matching the attributes BYTETracker reads from Ultralytics Boxes."""

    def __init__(self, detections: list[dict[str, Any]]):
        boxes: list[list[float]] = []
        scores: list[float] = []
        classes: list[int] = []
        for detection in detections:
            if int(detection.get("class_id", PERSON_CLASS_ID)) != PERSON_CLASS_ID:
                continue
            bbox = [float(v) for v in detection["bbox_xyxy"]]
            if len(bbox) != 4:
                raise ValueError("bbox_xyxy must contain [x1, y1, x2, y2]")
            boxes.append(bbox)
            scores.append(float(detection["confidence"]))
            classes.append(PERSON_CLASS_ID)

        xyxy = np.asarray(boxes, dtype=np.float32).reshape(-1, 4)
        self.xywh = np.column_stack(
            (
                (xyxy[:, 0] + xyxy[:, 2]) / 2,
                (xyxy[:, 1] + xyxy[:, 3]) / 2,
                xyxy[:, 2] - xyxy[:, 0],
                xyxy[:, 3] - xyxy[:, 1],
            )
        )
        self.conf = np.asarray(scores, dtype=np.float32)
        self.cls = np.asarray(classes, dtype=np.float32)


class ByteTrackZoneProcessor:
    """Keep ByteTrack state and count active person IDs inside configured zones."""

    def __init__(
        self,
        frame_rate: int = 30,
        track_high_thresh: float = 0.25,
        track_low_thresh: float = 0.1,
        new_track_thresh: float = 0.25,
        track_buffer: int = 30,
        match_thresh: float = 0.8,
        fuse_score: bool = True,
    ):
        if frame_rate <= 0:
            raise ValueError("frame_rate must be positive")
        args = SimpleNamespace(
            track_high_thresh=track_high_thresh,
            track_low_thresh=track_low_thresh,
            new_track_thresh=new_track_thresh,
            track_buffer=track_buffer,
            match_thresh=match_thresh,
            fuse_score=fuse_score,
        )
        try:
            self.tracker = BYTETracker(args=args, frame_rate=frame_rate)
        except TypeError as exc:
            if "frame_rate" not in str(exc):
                raise
            self.tracker = BYTETracker(args=args)

    def reset(self) -> None:
        self.tracker.reset()

    def update(self, detections: list[dict[str, Any]], zones: list[dict[str, Any]]) -> dict[str, Any]:
        tracked = self.tracker.update(_DetectionBatch(detections))
        tracks = [
            {
                "id": int(row[4]),
                "bbox_xyxy": [round(float(value), 2) for value in row[:4]],
                "confidence": round(float(row[5]), 4),
                "class_id": int(row[6]),
            }
            for row in tracked
        ]

        parsed_zones = [Zone.from_dict(zone) for zone in zones]
        metrics = []
        for zone in parsed_zones:
            count = sum(point_in_polygon(_foot_point(track["bbox_xyxy"]), zone.points) for track in tracks)
            status = "congested" if count >= zone.congest_at else "warning" if count >= zone.warn_at else "normal"
            metrics.append(
                {
                    "zoneId": zone.id,
                    "personCount": count,
                    "waitSec": count * zone.avg_service_sec,
                    "status": status,
                }
            )

        return {"tracks": tracks, "zones": metrics}


def _foot_point(bbox: list[float]) -> Point:
    x1, _, x2, y2 = bbox
    return ((x1 + x2) / 2, y2)

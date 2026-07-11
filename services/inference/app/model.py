import time

import torch
from PIL import Image
from ultralytics import YOLO

from app.schema import Detection
from app.utils import Settings

PERSON_CLASS_ID = 0
PERSON_CLASS_NAME = "person"


class YoloPersonDetector:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_ref = settings.model_path or settings.model_name
        self.device = self._resolve_device(settings.device)
        self.use_half = self.device.startswith("cuda")
        self.model = YOLO(self.model_ref)

    @staticmethod
    def _resolve_device(configured_device: str) -> str:
        if configured_device.lower() == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        if configured_device.lower().startswith("cuda") and not torch.cuda.is_available():
            return "cpu"
        return configured_device

    def predict(self, image: Image.Image) -> tuple[list[Detection], float]:
        started_at = time.perf_counter()
        results = self.model.predict(
            source=image,
            imgsz=self.settings.image_size,
            conf=self.settings.conf_thres,
            device=self.device,
            half=self.use_half,
            classes=[PERSON_CLASS_ID],
            verbose=False,
        )
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        return self._parse_detections(results), latency_ms

    @staticmethod
    def _parse_detections(results) -> list[Detection]:
        if not results:
            return []

        boxes = results[0].boxes
        if boxes is None:
            return []

        detections: list[Detection] = []
        for box in boxes:
            class_id = int(box.cls.item())
            if class_id != PERSON_CLASS_ID:
                continue

            detections.append(
                Detection(
                    class_id=PERSON_CLASS_ID,
                    class_name=PERSON_CLASS_NAME,
                    confidence=round(float(box.conf.item()), 4),
                    bbox_xyxy=[round(float(value), 2) for value in box.xyxy[0].tolist()],
                )
            )

        return detections

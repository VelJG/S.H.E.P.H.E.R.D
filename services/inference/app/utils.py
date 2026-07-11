import os
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError


@dataclass(frozen=True)
class Settings:
    model_name: str
    model_path: str | None
    image_size: int
    conf_thres: float
    device: str


def get_settings() -> Settings:
    model_path = os.getenv("MODEL_PATH") or None
    return Settings(
        model_name=os.getenv("MODEL_NAME", "yolo26s.pt"),
        model_path=model_path,
        image_size=int(os.getenv("IMG_SIZE", "640")),
        conf_thres=float(os.getenv("CONF_THRES", "0.25")),
        device=os.getenv("DEVICE", "auto"),
    )


def load_image(image_bytes: bytes) -> Image.Image:
    try:
        image = Image.open(BytesIO(image_bytes))
        return image.convert("RGB")
    except UnidentifiedImageError as exc:
        raise ValueError("Uploaded file is not a valid image") from exc

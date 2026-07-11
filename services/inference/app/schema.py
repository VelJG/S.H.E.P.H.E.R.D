from pydantic import BaseModel, Field


class Detection(BaseModel):
    class_id: int = Field(..., examples=[0])
    class_name: str = Field(..., examples=["person"])
    confidence: float = Field(..., examples=[0.87])
    bbox_xyxy: list[float] = Field(..., examples=[[120, 80, 260, 430]])


class InvocationResponse(BaseModel):
    model: str
    image_size: int
    detections: list[Detection]
    latency_ms: float


class PingResponse(BaseModel):
    status: str
    model: str
    device: str

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.model import YoloPersonDetector
from app.schema import InvocationResponse, PingResponse
from app.utils import get_settings, load_image


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.detector = YoloPersonDetector(settings)
    yield


app = FastAPI(title="S.H.E.P.H.E.R.D. YOLO Inference", version="0.1.0", lifespan=lifespan)


@app.get("/ping", response_model=PingResponse)
def ping() -> PingResponse:
    detector: YoloPersonDetector = app.state.detector
    return PingResponse(status="ok", model=detector.model_ref, device=detector.device)


@app.post("/invocations", response_model=InvocationResponse)
async def invocations(file: UploadFile = File(...)) -> InvocationResponse:
    detector: YoloPersonDetector = app.state.detector

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")

    try:
        image = load_image(image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    detections, latency_ms = detector.predict(image)
    return InvocationResponse(
        model=detector.model_ref,
        image_size=detector.settings.image_size,
        detections=detections,
        latency_ms=latency_ms,
    )

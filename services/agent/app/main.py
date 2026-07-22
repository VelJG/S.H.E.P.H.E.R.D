from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.data_store import LocalDataStore
from app.prediction import predict_all_zones
from app.schemas import AgentChatRequest, AgentChatResponse, Metric


def _default_data_dir() -> Path:
    configured = os.getenv("AGENT_DATA_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).parents[1] / "demo_data"


def _default_runtime_dir() -> Path:
    configured = os.getenv("AGENT_RUNTIME_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).parents[1] / "runtime_data"


def _cors_origins() -> list[str]:
    configured = os.getenv("AGENT_CORS_ORIGINS")
    if configured:
        return [item.strip() for item in configured.split(",") if item.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


def _normalize_ingest_payload(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "metrics" in payload:
        metrics = payload["metrics"]
        if not isinstance(metrics, list):
            raise HTTPException(status_code=422, detail="metrics must be an array")
        return metrics
    if isinstance(payload, dict):
        return [payload]
    raise HTTPException(status_code=422, detail="payload must be a metric, an array, or { metrics: [...] }")


def _metric_metadata(store: LocalDataStore) -> dict[str, dict[str, Any]]:
    return {
        item.zone_id: item.model_dump(by_alias=True, mode="json")
        for item in store.get_latest_metrics()
    }


def _build_prediction_answer(store: LocalDataStore) -> AgentChatResponse:
    predictions = predict_all_zones(store.get_zones(), store.get_metric_history(minutes=10))
    top = predictions[0] if predictions else None
    if top is None:
        answer = "No local metrics yet. Start the video processor or use seeded demo data."
    elif top.risk == "high" and top.eta_seconds == 0:
        answer = f"{top.zone_name} ({top.zone_id}) is congested now. {top.recommendation}"
    elif top.risk == "high":
        answer = f"{top.zone_name} ({top.zone_id}) is likely to congest in about {top.eta_seconds}s. {top.recommendation}"
    else:
        answer = f"No zone is critical yet. Top watch zone: {top.zone_name} ({top.zone_id}). {top.recommendation}"

    return AgentChatResponse(
        answer=answer,
        intent="predict",
        usedTools=["get_zones", "get_metric_history", "predict_all_zones"],
        predictions=predictions,
        metadata={"latestMetrics": _metric_metadata(store)},
    )


def _build_report_answer(store: LocalDataStore) -> AgentChatResponse:
    latest = store.get_latest_metrics()
    incidents = store.list_incidents()
    open_incidents = [item for item in incidents if item.status == "open"]
    busiest = max(latest, key=lambda item: item.person_count, default=None)
    avg_wait = round(sum(item.wait_sec for item in latest) / len(latest), 1) if latest else 0

    answer = (
        f"Shift summary: busiest zone is {busiest.zone_id if busiest else 'n/a'}, "
        f"average current wait is {avg_wait}s, total incidents {len(incidents)}, "
        f"open incidents {len(open_incidents)}. Recommendation: prioritize high-risk zones first."
    )
    return AgentChatResponse(
        answer=answer,
        intent="report",
        usedTools=["get_latest_metrics", "list_incidents"],
        metadata={
            "latestMetrics": _metric_metadata(store),
            "totalIncidents": len(incidents),
            "openIncidents": len(open_incidents),
            "averageWaitSec": avg_wait,
        },
    )


def _build_copilot_answer(store: LocalDataStore, request: AgentChatRequest) -> AgentChatResponse:
    latest = store.get_latest_metrics()
    busiest = max(latest, key=lambda item: item.person_count, default=None)
    open_incidents = store.list_open_incidents()
    if busiest:
        answer = (
            f"Busiest zone right now is {busiest.zone_id} with {busiest.person_count} people "
            f"and estimated wait {busiest.wait_sec}s. Open incidents: {len(open_incidents)}."
        )
    else:
        answer = "No local metric data is available yet."
    return AgentChatResponse(
        answer=answer,
        intent="copilot",
        usedTools=["get_latest_metrics", "list_open_incidents"],
        metadata={"latestMetrics": _metric_metadata(store), "question": request.message},
    )


def _detect_intent(request: AgentChatRequest) -> str:
    if request.mode != "auto":
        return request.mode
    message = request.message.lower()
    if any(term in message for term in ["predict", "prediction", "tắc", "congest", "nghẽn", "2 phút", "staff"]):
        return "predict"
    if any(term in message for term in ["report", "summary", "tóm tắt", "ca trực", "10 phút"]):
        return "report"
    return "copilot"


def create_app(data_dir: Path | None = None, runtime_dir: Path | None = None) -> FastAPI:
    store = LocalDataStore(data_dir or _default_data_dir(), runtime_dir or _default_runtime_dir())
    app = FastAPI(title="SHEPHERD Local Operations Agent", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/agent/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "shepherd-local-agent",
            "dataMode": "local-json",
            "zones": len(store.get_zones()),
        }

    @app.post("/agent/ingest/metrics")
    def ingest_metrics(payload: Any = Body(...)) -> dict[str, Any]:
        metrics = [Metric.model_validate(item) for item in _normalize_ingest_payload(payload)]
        written = store.append_metrics(metrics)
        return {"ok": True, "count": written}

    @app.post("/agent/chat", response_model=AgentChatResponse)
    def chat(request: AgentChatRequest) -> AgentChatResponse:
        intent = _detect_intent(request)
        if intent == "predict":
            return _build_prediction_answer(store)
        if intent == "report":
            return _build_report_answer(store)
        return _build_copilot_answer(store, request)

    @app.get("/agent/report", response_model=AgentChatResponse)
    def report() -> AgentChatResponse:
        return _build_report_answer(store)

    return app


app = create_app()

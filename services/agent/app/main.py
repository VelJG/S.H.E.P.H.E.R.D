from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.agent import ShepherdAgent
from app.data_store import LocalDataStore
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



def create_app(data_dir: Path | None = None, runtime_dir: Path | None = None) -> FastAPI:
    store = LocalDataStore(data_dir or _default_data_dir(), runtime_dir or _default_runtime_dir())
    agent = ShepherdAgent(store)
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
        return agent.chat(request.message, mode=request.mode)

    @app.get("/agent/report", response_model=AgentChatResponse)
    def report() -> AgentChatResponse:
        return agent.chat("Generate shift report", mode="report")

    return app


app = create_app()

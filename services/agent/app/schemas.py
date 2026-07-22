from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class Zone(CamelModel):
    zone_id: str = Field(alias="zoneId")
    zone_name: str = Field(alias="zoneName")
    warn_at: int = Field(alias="warnAt")
    congest_at: int = Field(alias="congestAt")
    avg_service_sec: int = Field(alias="avgServiceSec")


class Metric(CamelModel):
    zone_id: str = Field(alias="zoneId")
    timestamp: datetime
    person_count: int = Field(alias="personCount")
    queue_length: int = Field(alias="queueLength")
    wait_sec: int = Field(alias="waitSec")
    status: str = "normal"
    source: str = "demo-seed"
    congestion_score: float = Field(default=0.0, alias="congestionScore")


class Incident(CamelModel):
    incident_id: str = Field(alias="incidentId")
    zone_id: str = Field(alias="zoneId")
    zone_name: str = Field(alias="zoneName")
    status: str
    severity: str
    created_at: datetime = Field(alias="createdAt")
    title: str
    summary: str
    resolved_at: datetime | None = Field(default=None, alias="resolvedAt")


class Prediction(CamelModel):
    zone_id: str = Field(alias="zoneId")
    zone_name: str = Field(alias="zoneName")
    risk: Literal["low", "medium", "high"]
    eta_seconds: int | None = Field(alias="etaSeconds")
    reason: str
    recommendation: str


class AgentAlert(CamelModel):
    alert_id: str = Field(alias="alertId")
    zone_id: str = Field(alias="zoneId")
    zone_name: str = Field(alias="zoneName")
    status: Literal["open", "acknowledged", "resolved"] = "open"
    severity: Literal["medium", "high"] = "high"
    created_at: datetime = Field(alias="createdAt")
    eta_seconds: int | None = Field(default=None, alias="etaSeconds")
    reason: str
    recommendation: str
    used_tools: list[str] = Field(default_factory=list, alias="usedTools")
    source: str = "agent-monitor"


class AgentChatRequest(CamelModel):
    message: str
    session_id: str = Field(default="local-demo", alias="sessionId")
    mode: Literal["auto", "predict", "copilot", "report"] = "auto"


class AgentChatResponse(CamelModel):
    answer: str
    intent: str
    used_tools: list[str] = Field(default_factory=list, alias="usedTools")
    predictions: list[Prediction] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

from __future__ import annotations

import json
import re

from app.data_store import LocalDataStore
from app.llm import AgentModelClient
from app.schemas import AgentChatResponse
from app.tools import ShepherdTools


class ShepherdAgent:
    """Local deterministic operations agent for the hackathon presentation.

    The agentic boundary is here: it classifies user intent, chooses a short tool
    plan, calls tools, and synthesizes an operational answer. It deliberately
    works without OPENAI_API_KEY so the demo remains reliable.
    """

    def __init__(self, store: LocalDataStore, model_client: AgentModelClient | None = None):
        self.tools = ShepherdTools(store)
        self.model_client = model_client

    def chat(self, message: str, mode: str = "auto") -> AgentChatResponse:
        intent = self._detect_intent(message, mode)
        if intent == "predict":
            return self._predict(message)
        if intent == "report":
            return self._report(message)
        return self._copilot(message)

    def _detect_intent(self, message: str, mode: str = "auto") -> str:
        if mode in {"predict", "copilot", "report"}:
            return mode
        normalized = message.lower()
        if any(term in normalized for term in ["predict", "prediction", "dự đoán", "tắc", "congest", "nghẽn", "2 phút", "ngưỡng", "staff"]):
            return "predict"
        if any(term in normalized for term in ["report", "summary", "tóm tắt", "ca trực", "shift", "10 phút"]):
            return "report"
        return "copilot"

    def _predict(self, message: str) -> AgentChatResponse:
        predictions = self.tools.predict_congestion(minutes=10)
        recommendation = self.tools.recommend_staff_action(predictions)
        top = predictions[0] if predictions else None

        if top is None:
            answer = "No local metrics yet. Start the video processor or use seeded demo data."
        elif top.risk == "high" and top.eta_seconds == 0:
            answer = f"{top.zone_name} is congested now. {recommendation}"
        elif top.risk == "high":
            answer = f"{top.zone_name} is likely to congest in about {top.eta_seconds}s. {recommendation}"
        else:
            answer = f"No clear overcrowding issue yet. Watch {top.zone_name} for early signs of congestion. {recommendation}"

        response = AgentChatResponse(
            answer=answer,
            intent="predict",
            usedTools=["predict_congestion", "get_metric_history", "recommend_staff_action"],
            predictions=predictions,
            metadata={
                "question": message,
                "toolPlan": ["predict_congestion", "recommend_staff_action"],
                "latestMetrics": self.tools.latest_metrics_metadata(),
            },
        )
        return self._synthesize_with_ai(message, response)

    def _report(self, message: str) -> AgentChatResponse:
        report = self.tools.generate_shift_report()
        predictions = self.tools.predict_congestion(minutes=10)
        response = AgentChatResponse(
            answer=report["summary"],
            intent="report",
            usedTools=["generate_shift_report", "get_latest_metrics", "list_open_incidents", "predict_congestion"],
            predictions=predictions,
            metadata={
                "question": message,
                "toolPlan": ["generate_shift_report"],
                "latestMetrics": self.tools.latest_metrics_metadata(),
                **report,
            },
        )
        return self._synthesize_with_ai(message, response)

    def _copilot(self, message: str) -> AgentChatResponse:
        latest = self.tools.get_latest_metrics()
        open_incidents = self.tools.list_open_incidents()
        busiest = max(latest, key=lambda item: item.person_count, default=None)

        if busiest:
            answer = (
                f"Busiest area right now is {_metric_name(busiest)} with {busiest.person_count} people "
                f"and estimated wait {busiest.wait_sec}s. Open incidents: {len(open_incidents)}."
            )
        else:
            answer = "No local metric data is available yet."

        response = AgentChatResponse(
            answer=answer,
            intent="copilot",
            usedTools=["get_latest_metrics", "list_open_incidents"],
            metadata={
                "question": message,
                "toolPlan": ["get_latest_metrics", "list_open_incidents"],
                "latestMetrics": self.tools.latest_metrics_metadata(),
                "busiestZone": _metric_name(busiest) if busiest else None,
                "openIncidents": len(open_incidents),
            },
        )
        return self._synthesize_with_ai(message, response)


    def _synthesize_with_ai(self, message: str, response: AgentChatResponse) -> AgentChatResponse:
        if self.model_client is None:
            response.metadata["aiUsed"] = False
            response.metadata["aiProvider"] = "deterministic-fallback"
            response.answer = self._sanitize_user_answer(response.answer, response)
            return response

        system_prompt = (
            "You are SHEPHERD, an agentic AI venue-operations copilot. "
            "You receive tool outputs from live venue metrics, predictions, incidents, and reports. "
            "Answer like an operations dispatcher: concise, decisive, and action-oriented. "
            "Do not invent zones or numbers not present in the tool context. "
            "Answer only in English. "
            "Never mention internal zone IDs such as zone-123, upload-123, booth-1, booth-2, or entrance. Use zone names only. "
            "Do not mention tool names, JSON keys, implementation details, localhost, or backend internals. "
            "Avoid generic phrases like high risk/medium risk in the final answer. "
            "Say risk of overcrowding, signs of congestion, crowding pressure, or likely congestion instead. "
            "State where to send staff and why."
        )
        context = response.model_dump(by_alias=True, mode="json")
        user_prompt = (
            f"Operator question: {message}\n\n"
            "Tool result JSON:\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            "Rewrite the answer using the tool results. Keep it under 90 words."
        )
        try:
            answer = self.model_client.complete(system_prompt, user_prompt)
            if answer:
                response.answer = self._sanitize_user_answer(answer, response)
                response.metadata["aiUsed"] = True
                response.metadata["aiProvider"] = self.model_client.provider
                response.metadata["aiModel"] = self.model_client.model
                return response
        except Exception as exc:
            response.metadata["aiError"] = str(exc)

        response.metadata["aiUsed"] = False
        response.metadata["aiProvider"] = "deterministic-fallback"
        response.answer = self._sanitize_user_answer(response.answer, response)
        return response

    def _sanitize_user_answer(self, answer: str, response: AgentChatResponse) -> str:
        replacements: dict[str, str] = {}
        for prediction in response.predictions:
            replacements[prediction.zone_id] = prediction.zone_name
        for value in (response.metadata.get("latestMetrics") or {}).values():
            if isinstance(value, dict):
                zone_name = value.get("zoneName")
                zone_id = value.get("zoneId")
                if zone_id and zone_name:
                    replacements[str(zone_id)] = str(zone_name)
        sanitized = answer
        for zone_id, zone_name in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
            sanitized = sanitized.replace(zone_id, zone_name)
        sanitized = re.sub(r"\b(?:zone|upload)-[A-Za-z0-9]+\b", "the selected area", sanitized)
        sanitized = re.sub(r"\bbooth-\d+\b", "the selected area", sanitized, flags=re.IGNORECASE)
        return sanitized


def _metric_name(metric) -> str:
    zone_name = getattr(metric, "zone_name", None)
    if zone_name:
        return zone_name
    zone_id = str(getattr(metric, "zone_id", "selected area")).replace("_", "-")
    if zone_id.startswith("zone-"):
        return f"Live Zone {zone_id.removeprefix('zone-')}"
    if zone_id.startswith("upload-"):
        return f"Upload Zone {zone_id.removeprefix('upload-')}"
    if zone_id.startswith("booth-"):
        return f"Booth {zone_id.removeprefix('booth-')}"
    return zone_id.replace("-", " ").title()

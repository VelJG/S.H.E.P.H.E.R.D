from __future__ import annotations

from app.data_store import LocalDataStore
from app.schemas import AgentChatResponse
from app.tools import ShepherdTools


class ShepherdAgent:
    """Local deterministic operations agent for the hackathon presentation.

    The agentic boundary is here: it classifies user intent, chooses a short tool
    plan, calls tools, and synthesizes an operational answer. It deliberately
    works without OPENAI_API_KEY so the demo remains reliable.
    """

    def __init__(self, store: LocalDataStore):
        self.tools = ShepherdTools(store)

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
            answer = f"{top.zone_name} ({top.zone_id}) is congested now. {recommendation}"
        elif top.risk == "high":
            answer = f"{top.zone_name} ({top.zone_id}) is likely to congest in about {top.eta_seconds}s. {recommendation}"
        else:
            answer = f"No zone is critical yet. Top watch zone: {top.zone_name} ({top.zone_id}). {recommendation}"

        return AgentChatResponse(
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

    def _report(self, message: str) -> AgentChatResponse:
        report = self.tools.generate_shift_report()
        predictions = self.tools.predict_congestion(minutes=10)
        return AgentChatResponse(
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

    def _copilot(self, message: str) -> AgentChatResponse:
        latest = self.tools.get_latest_metrics()
        open_incidents = self.tools.list_open_incidents()
        busiest = max(latest, key=lambda item: item.person_count, default=None)

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
            metadata={
                "question": message,
                "toolPlan": ["get_latest_metrics", "list_open_incidents"],
                "latestMetrics": self.tools.latest_metrics_metadata(),
                "busiestZone": busiest.zone_id if busiest else None,
                "openIncidents": len(open_incidents),
            },
        )

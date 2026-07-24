from __future__ import annotations

from typing import Any

from app.data_store import LocalDataStore
from app.prediction import predict_all_zones
from app.schemas import Incident, Metric, Prediction


class ShepherdTools:
    """Deterministic operational tools available to the local SHEPHERD agent.

    This mirrors the production AgentCore story: the agent decides which tool to
    call, while each tool has a narrow, testable responsibility over venue data.
    """

    def __init__(self, store: LocalDataStore):
        self.store = store

    def get_latest_metrics(self) -> list[Metric]:
        return self.store.get_latest_metrics()

    def get_metric_history(self, minutes: int = 10, zone_id: str | None = None) -> list[Metric]:
        return self.store.get_metric_history(zone_id=zone_id, minutes=minutes)

    def list_open_incidents(self) -> list[Incident]:
        return self.store.list_open_incidents()

    def predict_congestion(self, minutes: int = 10) -> list[Prediction]:
        return predict_all_zones(self.store.get_zones(), self.get_metric_history(minutes=minutes))

    def recommend_staff_action(self, predictions: list[Prediction] | None = None) -> str:
        predictions = predictions if predictions is not None else self.predict_congestion()
        if not predictions:
            return "Keep normal monitoring until live metrics arrive."
        top = predictions[0]
        return top.recommendation

    def generate_shift_report(self) -> dict[str, Any]:
        latest = self.get_latest_metrics()
        incidents = self.store.list_incidents()
        open_incidents = [item for item in incidents if item.status == "open"]
        busiest = max(latest, key=lambda item: item.person_count, default=None)
        avg_wait = round(sum(item.wait_sec for item in latest) / len(latest), 1) if latest else 0
        predictions = self.predict_congestion()
        high_risk = [item for item in predictions if item.risk == "high"]

        recommendation = (
            high_risk[0].recommendation
            if high_risk
            else "No urgent overcrowding detected. Keep one staff member watching queues with early signs of congestion."
        )
        summary = (
            f"Shift summary: busiest zone is {busiest.zone_id if busiest else 'n/a'}, "
            f"average current wait is {avg_wait}s, total incidents {len(incidents)}, "
            f"open incidents {len(open_incidents)}. Recommendation: {recommendation}"
        )

        return {
            "summary": summary,
            "busiestZone": busiest.zone_id if busiest else None,
            "averageWaitSec": avg_wait,
            "totalIncidents": len(incidents),
            "openIncidents": len(open_incidents),
            "overcrowdingWatchZones": [item.zone_id for item in high_risk],
            "recommendation": recommendation,
        }

    def latest_metrics_metadata(self) -> dict[str, dict[str, Any]]:
        return {
            item.zone_id: item.model_dump(by_alias=True, mode="json")
            for item in self.get_latest_metrics()
        }

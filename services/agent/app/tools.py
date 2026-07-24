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
        history = self.get_metric_history(minutes=5)
        incidents = self.store.list_incidents()
        open_incidents = [item for item in incidents if item.status == "open"]
        recent_stats = self.recent_zone_stats(minutes=5)
        busiest_stat = max(recent_stats, key=lambda item: item["peakPersonCount"], default=None)
        busiest = max(latest, key=lambda item: item.person_count, default=None)
        avg_wait = round(sum(item.wait_sec for item in latest) / len(latest), 1) if latest else 0
        predictions = self.predict_congestion()
        high_risk = [item for item in predictions if item.risk == "high"]

        recommendation = (
            high_risk[0].recommendation
            if high_risk
            else "No urgent overcrowding detected. Keep one staff member watching queues with early signs of congestion."
        )
        if busiest_stat:
            busiest_label = str(busiest_stat["zoneName"])
            peak_count = int(busiest_stat["peakPersonCount"])
            current_count = int(busiest_stat["currentPersonCount"])
            peak_status = str(busiest_stat["peakStatus"])
            summary = (
                f"Current shift report: {busiest_label} was the busiest area in the recent window, "
                f"peaking at {peak_count} people and currently showing {current_count} people. "
                f"Peak status was {peak_status}. Average current wait is {avg_wait}s. "
                f"Open incidents: {len(open_incidents)}. Recommendation: {recommendation}"
            )
        else:
            summary = (
                "Current shift report: no live zone metrics are available yet. "
                "Start live tracking, then ask again for current people counts and timing."
            )

        return {
            "summary": summary,
            "busiestZone": (busiest_stat or {}).get("zoneName") or _metric_display_name(busiest),
            "averageWaitSec": avg_wait,
            "totalIncidents": len(incidents),
            "openIncidents": len(open_incidents),
            "overcrowdingWatchZones": [item.zone_name for item in high_risk],
            "recommendation": recommendation,
            "recentZoneStats": recent_stats,
            "recentMetricSamples": len(history),
        }

    def latest_metrics_metadata(self) -> dict[str, dict[str, Any]]:
        return {
            _metric_display_name(item): {
                "zoneName": _metric_display_name(item),
                "timestamp": item.timestamp.isoformat(),
                "personCount": item.person_count,
                "queueLength": item.queue_length,
                "waitSec": item.wait_sec,
                "status": item.status,
                "congestionScore": item.congestion_score,
            }
            for item in self.get_latest_metrics()
        }

    def recent_zone_stats(self, minutes: int = 5) -> list[dict[str, Any]]:
        latest_by_zone = {item.zone_id: item for item in self.get_latest_metrics()}
        grouped: dict[str, list[Metric]] = {}
        for metric in self.get_metric_history(minutes=minutes):
            grouped.setdefault(metric.zone_id, []).append(metric)

        stats: list[dict[str, Any]] = []
        for zone_id, metrics in grouped.items():
            ordered = sorted(metrics, key=lambda item: item.timestamp)
            latest = latest_by_zone.get(zone_id) or ordered[-1]
            peak = max(ordered, key=lambda item: item.person_count)
            stats.append({
                "zoneName": _metric_display_name(latest),
                "currentPersonCount": latest.person_count,
                "peakPersonCount": peak.person_count,
                "currentWaitSec": latest.wait_sec,
                "peakWaitSec": peak.wait_sec,
                "currentStatus": latest.status,
                "peakStatus": peak.status,
                "lastUpdated": latest.timestamp.isoformat(),
                "sampleCount": len(ordered),
            })
        return sorted(stats, key=lambda item: (-int(item["peakPersonCount"]), str(item["zoneName"])))


def _metric_display_name(metric: Metric | None) -> str | None:
    if metric is None:
        return None
    if metric.zone_name:
        return metric.zone_name
    zone_id = metric.zone_id.replace("_", "-")
    if zone_id.startswith("zone-"):
        return f"Live Zone {zone_id.removeprefix('zone-')}"
    if zone_id.startswith("upload-"):
        return f"Upload Zone {zone_id.removeprefix('upload-')}"
    if zone_id.startswith("booth-"):
        return f"Booth {zone_id.removeprefix('booth-')}"
    return zone_id.replace("-", " ").title()

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.data_store import LocalDataStore
from app.schemas import AgentAlert
from app.tools import ShepherdTools


class AgentMonitor:
    """Autonomous local monitor that proactively creates agent alerts."""

    def __init__(self, store: LocalDataStore):
        self.store = store
        self.tools = ShepherdTools(store)

    def run_once(self) -> AgentAlert | None:
        predictions = self.tools.predict_congestion(minutes=10)
        top = predictions[0] if predictions else None
        if top is None or top.risk != "high":
            return None

        open_alerts = self.store.list_agent_alerts(status="open", limit=50)
        if any(alert.zone_id == top.zone_id for alert in open_alerts):
            return None

        created_at = datetime.now(timezone.utc)
        alert = AgentAlert(
            alertId=f"AGENT-{created_at.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}",
            zoneId=top.zone_id,
            zoneName=top.zone_name,
            status="open",
            severity="high",
            createdAt=created_at,
            etaSeconds=top.eta_seconds,
            reason=top.reason,
            recommendation=top.recommendation,
            usedTools=["predict_congestion", "recommend_staff_action", "append_agent_alert"],
            source="agent-monitor",
        )
        return self.store.append_agent_alert(alert)

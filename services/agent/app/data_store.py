from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from app.schemas import AgentAlert, Incident, Metric, Zone


class LocalDataStore:
    """Local JSON-backed store for presentation-safe agent data.

    Seed data lives in demo_data/*.json. Runtime live metrics are appended to
    runtime_data/metrics.jsonl. Once runtime metrics exist, the agent treats
    them as the active demo state so old seed data cannot dominate live answers.
    """

    def __init__(self, data_dir: Path, runtime_dir: Path | None = None):
        self.data_dir = Path(data_dir)
        self.runtime_dir = Path(runtime_dir) if runtime_dir else self.data_dir.parent / "runtime_data"
        self.runtime_metrics_path = self.runtime_dir / "metrics.jsonl"
        self.runtime_alerts_path = self.runtime_dir / "agent_alerts.jsonl"

    def _read_json_array(self, name: str) -> list[dict]:
        path = self.data_dir / name
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, list):
            raise ValueError(f"{path} must contain a JSON array")
        return value

    def _read_jsonl_objects(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        items: list[dict] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
                if not isinstance(value, dict):
                    raise ValueError(f"JSONL item at {path}:{line_number} must be an object")
                items.append(value)
        return items

    def _read_runtime_metrics(self) -> list[dict]:
        return self._read_jsonl_objects(self.runtime_metrics_path)

    def has_runtime_metrics(self) -> bool:
        return bool(self._read_runtime_metrics())

    def get_zones(self) -> list[Zone]:
        if self.has_runtime_metrics():
            return [
                Zone(
                    zoneId=metric.zone_id,
                    zoneName=metric.zone_name or _humanize_zone_id(metric.zone_id),
                    warnAt=_runtime_warn_at(metric),
                    congestAt=_runtime_congest_at(metric),
                    avgServiceSec=20,
                )
                for metric in self.get_latest_metrics()
            ]
        return [Zone.model_validate(item) for item in self._read_json_array("zones.json")]

    def get_metric_history(self, zone_id: str | None = None, minutes: int = 10) -> list[Metric]:
        runtime_items = self._read_runtime_metrics()
        raw_items = runtime_items if runtime_items else self._read_json_array("metrics.json")
        items = [Metric.model_validate(item) for item in raw_items]
        if zone_id:
            items = [item for item in items if item.zone_id == zone_id]
        items.sort(key=lambda item: item.timestamp)
        return items[-max(1, minutes * 3):]

    def get_latest_metrics(self) -> list[Metric]:
        latest: dict[str, Metric] = {}
        zone_names: dict[str, str] = {}
        for item in self.get_metric_history(minutes=60):
            if item.zone_name:
                zone_names[item.zone_id] = item.zone_name
            current = latest.get(item.zone_id)
            if current is None or item.timestamp > current.timestamp:
                latest[item.zone_id] = item
        named_latest = [
            item if item.zone_name else item.model_copy(update={"zone_name": zone_names.get(item.zone_id)})
            for item in latest.values()
        ]
        return sorted(named_latest, key=lambda item: item.zone_id)

    def list_open_incidents(self) -> list[Incident]:
        return [item for item in self.list_incidents() if item.status == "open"]

    def list_incidents(self) -> list[Incident]:
        if self.has_runtime_metrics():
            return []
        items = [Incident.model_validate(item) for item in self._read_json_array("incidents.json")]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def append_metrics(self, metrics: Iterable[Metric | dict]) -> int:
        parsed = [item if isinstance(item, Metric) else Metric.model_validate(item) for item in metrics]
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        with self.runtime_metrics_path.open("a", encoding="utf-8") as handle:
            for metric in parsed:
                payload = metric.model_dump(by_alias=True, mode="json")
                handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        return len(parsed)

    def append_agent_alert(self, alert: AgentAlert | dict) -> AgentAlert:
        parsed = alert if isinstance(alert, AgentAlert) else AgentAlert.model_validate(alert)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        payload = parsed.model_dump(by_alias=True, mode="json")
        with self.runtime_alerts_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        return parsed

    def list_agent_alerts(self, status: str | None = None, limit: int = 20) -> list[AgentAlert]:
        items = [AgentAlert.model_validate(item) for item in self._read_jsonl_objects(self.runtime_alerts_path)]
        if self.has_runtime_metrics():
            active_zone_ids = {item.zone_id for item in self.get_latest_metrics()}
            items = [item for item in items if item.zone_id in active_zone_ids]
        if status:
            items = [item for item in items if item.status == status]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items[:max(1, limit)]


def _default_store() -> LocalDataStore:
    return LocalDataStore(Path(__file__).parents[1] / "demo_data")


def _humanize_zone_id(zone_id: str) -> str:
    cleaned = zone_id.replace("_", "-")
    if cleaned.startswith("zone-"):
        return f"Live Zone {cleaned.removeprefix('zone-')}"
    if cleaned.startswith("upload-"):
        return f"Upload Zone {cleaned.removeprefix('upload-')}"
    return cleaned.replace("-", " ").title()


def _runtime_warn_at(metric: Metric) -> int:
    if metric.status == "congested":
        return max(1, metric.person_count - 1)
    return max(1, metric.person_count)


def _runtime_congest_at(metric: Metric) -> int:
    if metric.status == "congested":
        return max(1, metric.person_count)
    return max(2, metric.person_count + 1)


if __name__ == "__main__":
    store = _default_store()
    print("SHEPHERD local data store OK")
    print(f"zones={len(store.get_zones())}")
    print(f"latestMetrics={len(store.get_latest_metrics())}")
    print(f"openIncidents={len(store.list_open_incidents())}")
    for metric in store.get_latest_metrics():
        print(f"- {metric.zone_id}: count={metric.person_count} wait={metric.wait_sec}s status={metric.status} source={metric.source}")

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from app.schemas import Incident, Metric, Zone


class LocalDataStore:
    """Local JSON-backed store for presentation-safe agent data.

    Seed data lives in demo_data/*.json. Runtime live metrics are appended to
    runtime_data/metrics.jsonl and merged with the seed history when queried.
    """

    def __init__(self, data_dir: Path, runtime_dir: Path | None = None):
        self.data_dir = Path(data_dir)
        self.runtime_dir = Path(runtime_dir) if runtime_dir else self.data_dir.parent / "runtime_data"
        self.runtime_metrics_path = self.runtime_dir / "metrics.jsonl"

    def _read_json_array(self, name: str) -> list[dict]:
        path = self.data_dir / name
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, list):
            raise ValueError(f"{path} must contain a JSON array")
        return value

    def _read_runtime_metrics(self) -> list[dict]:
        if not self.runtime_metrics_path.exists():
            return []
        items: list[dict] = []
        with self.runtime_metrics_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at {self.runtime_metrics_path}:{line_number}") from exc
                if not isinstance(value, dict):
                    raise ValueError(f"Runtime metric at {self.runtime_metrics_path}:{line_number} must be an object")
                items.append(value)
        return items

    def get_zones(self) -> list[Zone]:
        return [Zone.model_validate(item) for item in self._read_json_array("zones.json")]

    def get_metric_history(self, zone_id: str | None = None, minutes: int = 10) -> list[Metric]:
        raw_items = self._read_json_array("metrics.json") + self._read_runtime_metrics()
        items = [Metric.model_validate(item) for item in raw_items]
        if zone_id:
            items = [item for item in items if item.zone_id == zone_id]
        items.sort(key=lambda item: item.timestamp)
        return items[-max(1, minutes * 3):]

    def get_latest_metrics(self) -> list[Metric]:
        latest: dict[str, Metric] = {}
        for item in self.get_metric_history(minutes=60):
            current = latest.get(item.zone_id)
            if current is None or item.timestamp > current.timestamp:
                latest[item.zone_id] = item
        return sorted(latest.values(), key=lambda item: item.zone_id)

    def list_open_incidents(self) -> list[Incident]:
        return [item for item in self.list_incidents() if item.status == "open"]

    def list_incidents(self) -> list[Incident]:
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


def _default_store() -> LocalDataStore:
    return LocalDataStore(Path(__file__).parents[1] / "demo_data")


if __name__ == "__main__":
    store = _default_store()
    print("SHEPHERD local data store OK")
    print(f"zones={len(store.get_zones())}")
    print(f"latestMetrics={len(store.get_latest_metrics())}")
    print(f"openIncidents={len(store.list_open_incidents())}")
    for metric in store.get_latest_metrics():
        print(f"- {metric.zone_id}: count={metric.person_count} wait={metric.wait_sec}s status={metric.status} source={metric.source}")

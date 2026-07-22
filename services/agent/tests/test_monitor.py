from pathlib import Path

from app.data_store import LocalDataStore
from app.monitor import AgentMonitor


def test_monitor_creates_alert_for_high_risk_zone(tmp_path: Path):
    store = LocalDataStore(Path(__file__).parents[1] / "demo_data", runtime_dir=tmp_path / "runtime_data")
    monitor = AgentMonitor(store)

    alert = monitor.run_once()

    assert alert is not None
    assert alert.zone_id == "booth-2"
    assert alert.status == "open"
    assert alert.severity == "high"
    assert "staff" in alert.recommendation.lower()
    assert "predict_congestion" in alert.used_tools
    assert store.list_agent_alerts()[0].alert_id == alert.alert_id


def test_monitor_deduplicates_open_alert_for_same_zone(tmp_path: Path):
    store = LocalDataStore(Path(__file__).parents[1] / "demo_data", runtime_dir=tmp_path / "runtime_data")
    monitor = AgentMonitor(store)

    first = monitor.run_once()
    second = monitor.run_once()

    assert first is not None
    assert second is None
    assert len(store.list_agent_alerts(status="open")) == 1

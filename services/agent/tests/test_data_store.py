from pathlib import Path

from app.data_store import LocalDataStore


def store(tmp_path: Path) -> LocalDataStore:
    return LocalDataStore(Path(__file__).parents[1] / "demo_data", runtime_dir=tmp_path / "runtime_data")


def test_latest_metrics_returns_one_per_zone(tmp_path: Path):
    items = store(tmp_path).get_latest_metrics()
    assert {item.zone_id for item in items} == {"booth-1", "booth-2", "entrance"}
    assert next(item for item in items if item.zone_id == "booth-2").person_count == 6


def test_history_filters_zone(tmp_path: Path):
    items = store(tmp_path).get_metric_history(zone_id="booth-2", minutes=10)
    assert len(items) == 3
    assert all(item.zone_id == "booth-2" for item in items)


def test_open_incidents_filters_status(tmp_path: Path):
    items = store(tmp_path).list_open_incidents()
    assert len(items) == 1
    assert items[0].incident_id == "inc-001"


def test_append_metrics_writes_runtime_jsonl(tmp_path: Path):
    data_dir = Path(__file__).parents[1] / "demo_data"
    runtime_dir = tmp_path / "runtime_data"
    subject = LocalDataStore(data_dir, runtime_dir=runtime_dir)

    written = subject.append_metrics([
        {
            "zoneId": "booth-2",
            "timestamp": "2026-07-22T14:02:00+07:00",
            "personCount": 8,
            "queueLength": 8,
            "waitSec": 140,
            "status": "congested",
            "source": "test-live",
        }
    ])

    assert written == 1
    runtime_file = runtime_dir / "metrics.jsonl"
    assert runtime_file.exists()
    latest = subject.get_latest_metrics()
    booth_2 = next(item for item in latest if item.zone_id == "booth-2")
    assert booth_2.person_count == 8
    assert booth_2.source == "test-live"


def test_runtime_metrics_replace_seed_demo_state(tmp_path: Path):
    data_dir = Path(__file__).parents[1] / "demo_data"
    runtime_dir = tmp_path / "runtime_data"
    subject = LocalDataStore(data_dir, runtime_dir=runtime_dir)

    subject.append_metrics([
        {
            "zoneId": "upload-zone",
            "zoneName": "Crowd Area",
            "timestamp": "2026-07-24T16:30:00Z",
            "personCount": 2,
            "queueLength": 2,
            "waitSec": 40,
            "status": "normal",
            "source": "frontend-live",
        }
    ])

    latest = subject.get_latest_metrics()
    assert {item.zone_id for item in latest} == {"upload-zone"}
    zones = subject.get_zones()
    assert [(item.zone_id, item.zone_name) for item in zones] == [("upload-zone", "Crowd Area")]
    assert subject.list_open_incidents() == []


def test_latest_metrics_preserve_runtime_zone_name(tmp_path: Path):
    data_dir = Path(__file__).parents[1] / "demo_data"
    runtime_dir = tmp_path / "runtime_data"
    subject = LocalDataStore(data_dir, runtime_dir=runtime_dir)

    subject.append_metrics([
        {
            "zoneId": "zone-123",
            "zoneName": "Crowd Entrance",
            "timestamp": "2026-07-24T16:30:00Z",
            "personCount": 10,
            "queueLength": 10,
            "waitSec": 200,
            "status": "congested",
            "source": "frontend-live",
        },
        {
            "zoneId": "zone-123",
            "timestamp": "2026-07-24T16:30:01Z",
            "personCount": 9,
            "queueLength": 9,
            "waitSec": 180,
            "status": "congested",
            "source": "frontend-live",
        },
    ])

    [latest] = subject.get_latest_metrics()
    assert latest.zone_name == "Crowd Entrance"
    [zone] = subject.get_zones()
    assert zone.zone_name == "Crowd Entrance"

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def client(tmp_path: Path) -> TestClient:
    app = create_app(
        data_dir=Path(__file__).parents[1] / "demo_data",
        runtime_dir=tmp_path / "runtime_data",
        enable_monitor=False,
    )
    return TestClient(app)


def test_agent_monitor_route_creates_alert(tmp_path: Path):
    subject = client(tmp_path)

    response = subject.post("/agent/monitor/run")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["alert"]["zoneId"] == "booth-2"


def test_agent_alerts_route_returns_alerts(tmp_path: Path):
    subject = client(tmp_path)
    subject.post("/agent/monitor/run")

    response = subject.get("/agent/alerts")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["alerts"][0]["status"] == "open"

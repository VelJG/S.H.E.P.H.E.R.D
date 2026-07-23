from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def client(tmp_path: Path) -> TestClient:
    app = create_app(
        data_dir=Path(__file__).parents[1] / "demo_data",
        runtime_dir=tmp_path / "runtime_data",
        enable_ai=False,
    )
    return TestClient(app)


def test_health_returns_ok(tmp_path: Path):
    response = client(tmp_path).get("/agent/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_chat_prediction_returns_predictions(tmp_path: Path):
    response = client(tmp_path).post(
        "/agent/chat",
        json={"message": "Booth nào sẽ tắc trong 2 phút tới?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "predict"
    assert body["predictions"]
    assert body["predictions"][0]["zoneId"] == "booth-2"
    assert "Booth" in body["answer"] or "booth" in body["answer"]


def test_ingest_single_metric_affects_chat(tmp_path: Path):
    subject = client(tmp_path)

    ingest_response = subject.post(
        "/agent/ingest/metrics",
        json={
            "zoneId": "booth-2",
            "timestamp": "2026-07-22T14:02:00+07:00",
            "personCount": 8,
            "queueLength": 8,
            "waitSec": 140,
            "status": "congested",
            "source": "api-test",
        },
    )
    assert ingest_response.status_code == 200
    ingest_body = ingest_response.json()
    assert ingest_body["ok"] is True
    assert ingest_body["count"] == 1
    assert ingest_body["alert"]["zoneId"] == "booth-2"

    chat_response = subject.post("/agent/chat", json={"message": "Booth nào đang tắc?"})
    body = chat_response.json()
    assert "booth-2" in body["answer"] or "AI Demo Booth" in body["answer"]
    assert body["metadata"]["latestMetrics"]["booth-2"]["personCount"] == 8


def test_ingest_metrics_wrapper(tmp_path: Path):
    response = client(tmp_path).post(
        "/agent/ingest/metrics",
        json={
            "metrics": [
                {
                    "zoneId": "entrance",
                    "timestamp": "2026-07-22T14:03:00+07:00",
                    "personCount": 9,
                    "queueLength": 9,
                    "waitSec": 50,
                    "status": "warning",
                    "source": "api-test",
                }
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["count"] == 1
    assert "alert" in body

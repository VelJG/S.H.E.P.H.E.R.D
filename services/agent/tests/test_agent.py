from pathlib import Path

from app.agent import ShepherdAgent
from app.data_store import LocalDataStore


def agent() -> ShepherdAgent:
    store = LocalDataStore(Path(__file__).parents[1] / "demo_data", runtime_dir=Path(__file__).parents[1] / ".pytest_runtime")
    return ShepherdAgent(store)


def test_prediction_question_uses_prediction_tools(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = agent().chat("Booth nào sẽ tắc trong 2 phút tới?")

    assert response.intent == "predict"
    assert "predict_congestion" in response.used_tools
    assert "recommend_staff_action" in response.used_tools
    assert response.predictions[0].zone_id == "booth-2"
    assert "staff" in response.answer.lower()


def test_report_question_uses_shift_report_tool():
    response = agent().chat("Tóm tắt 10 phút qua", mode="auto")

    assert response.intent == "report"
    assert "generate_shift_report" in response.used_tools
    assert response.metadata["totalIncidents"] == 2
    assert response.metadata["openIncidents"] == 1


def test_copilot_question_returns_busiest_zone():
    response = agent().chat("Booth nào đông nhất?")

    assert response.intent == "copilot"
    assert "get_latest_metrics" in response.used_tools
    assert "Entrance" in response.answer
    assert response.metadata["busiestZone"] == "Entrance"


def test_explicit_predict_mode_overrides_message():
    response = agent().chat("hello", mode="predict")

    assert response.intent == "predict"
    assert response.predictions

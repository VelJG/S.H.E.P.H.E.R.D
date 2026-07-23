from pathlib import Path

from app.agent import ShepherdAgent
from app.data_store import LocalDataStore


class FakeModelClient:
    provider = "fake-llm"
    model = "fake-model"

    def __init__(self):
        self.calls = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system": system_prompt, "user": user_prompt})
        return "AI Agent says: send staff to Booth 2 now and redirect traffic."


def store() -> LocalDataStore:
    return LocalDataStore(Path(__file__).parents[1] / "demo_data")


def test_agent_uses_llm_when_model_client_is_available():
    model = FakeModelClient()
    agent = ShepherdAgent(store(), model_client=model)

    response = agent.chat("Nên gửi staff đi đâu?")

    assert model.calls, "expected the LLM client to be called"
    assert response.answer.startswith("AI Agent says:")
    assert response.metadata["aiProvider"] == "fake-llm"
    assert response.metadata["aiModel"] == "fake-model"
    assert response.metadata["aiUsed"] is True
    assert "predict_congestion" in model.calls[0]["user"]


def test_agent_falls_back_when_llm_fails():
    class BrokenModel(FakeModelClient):
        provider = "broken"
        model = "broken-model"

        def complete(self, system_prompt: str, user_prompt: str) -> str:
            raise RuntimeError("network down")

    response = ShepherdAgent(store(), model_client=BrokenModel()).chat("Nên gửi staff đi đâu?")

    assert response.metadata["aiUsed"] is False
    assert response.metadata["aiProvider"] == "deterministic-fallback"
    assert "aiError" in response.metadata
    assert "staff" in response.answer.lower()

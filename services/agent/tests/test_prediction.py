from pathlib import Path

from app.data_store import LocalDataStore
from app.prediction import predict_all_zones


def test_predict_all_zones_flags_booth_2_as_high_risk():
    store = LocalDataStore(Path(__file__).parents[1] / "demo_data")

    predictions = predict_all_zones(store.get_zones(), store.get_metric_history(minutes=10))

    booth_2 = next(item for item in predictions if item.zone_id == "booth-2")
    assert booth_2.risk == "high"
    assert booth_2.eta_seconds is not None
    assert booth_2.eta_seconds <= 120
    assert "staff" in booth_2.recommendation.lower()

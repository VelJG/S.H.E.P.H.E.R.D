from __future__ import annotations

from collections import defaultdict

from app.schemas import Metric, Prediction, Zone


def _trend_people_per_second(history: list[Metric]) -> float:
    if len(history) < 2:
        return 0.0
    first = history[0]
    last = history[-1]
    elapsed = (last.timestamp - first.timestamp).total_seconds()
    if elapsed <= 0:
        return 0.0
    return (last.person_count - first.person_count) / elapsed


def predict_zone(zone: Zone, history: list[Metric]) -> Prediction:
    if not history:
        return Prediction(
            zoneId=zone.zone_id,
            zoneName=zone.zone_name,
            risk="low",
            etaSeconds=None,
            reason="No recent metric history is available for this zone.",
            recommendation="Keep normal monitoring until live metrics arrive.",
        )

    history = sorted(history, key=lambda item: item.timestamp)
    latest = history[-1]
    trend_per_second = _trend_people_per_second(history)
    remaining = zone.congest_at - latest.person_count

    if latest.person_count >= zone.congest_at:
        eta_seconds = 0
        risk = "high"
        reason = f"{zone.zone_name} is already at {latest.person_count}/{zone.congest_at} people."
    elif trend_per_second > 0:
        eta_seconds = max(1, round(remaining / trend_per_second))
        if eta_seconds <= 120:
            risk = "high"
        elif latest.person_count >= zone.warn_at or eta_seconds <= 300:
            risk = "medium"
        else:
            risk = "low"
        reason = (
            f"{zone.zone_name} is at {latest.person_count}/{zone.congest_at} people "
            f"and rising about {trend_per_second * 60:.1f} people/min."
        )
    else:
        eta_seconds = None
        risk = "medium" if latest.person_count >= zone.warn_at else "low"
        reason = f"{zone.zone_name} is stable at {latest.person_count}/{zone.congest_at} people."

    if risk == "high":
        recommendation = f"Send 1 staff member to {zone.zone_name} now and redirect arrivals to a quieter zone."
    elif risk == "medium":
        recommendation = f"Keep {zone.zone_name} on watch and prepare one staff member if the queue keeps growing."
    else:
        recommendation = f"No action needed for {zone.zone_name}; keep normal monitoring."

    return Prediction(
        zoneId=zone.zone_id,
        zoneName=zone.zone_name,
        risk=risk,
        etaSeconds=eta_seconds,
        reason=reason,
        recommendation=recommendation,
    )


def predict_all_zones(zones: list[Zone], history: list[Metric]) -> list[Prediction]:
    by_zone: dict[str, list[Metric]] = defaultdict(list)
    for metric in history:
        by_zone[metric.zone_id].append(metric)

    predictions = [predict_zone(zone, by_zone.get(zone.zone_id, [])) for zone in zones]
    risk_rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(
        predictions,
        key=lambda item: (
            risk_rank[item.risk],
            item.eta_seconds if item.eta_seconds is not None else 999999,
            item.zone_id,
        ),
    )

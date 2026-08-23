from __future__ import annotations

from dataclasses import dataclass


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class SensorAssessment:
    name: str
    trust_score: float
    status: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "trust_score": round(self.trust_score, 1),
            "status": self.status,
            "reason": self.reason,
        }


def _status(score: float) -> str:
    if score >= 80:
        return "TRUSTED"
    if score >= 55:
        return "CHECK"
    return "SUSPECT"


def assess_sensor_health(telemetry: dict, twin: dict) -> dict:
    """Prototype cross-sensor consistency checks.

    This does not replace certified sensor diagnostics. It is intentionally
    conservative and only flags strong inconsistencies in related signals.
    """

    z = twin["z_scores"]
    results: list[SensorAssessment] = []

    # EGT channels should usually move together. A single extreme channel while
    # the other two are close to reference is more consistent with a channel
    # issue than a global thermal event.
    egt_names = ["EGT1", "EGT2", "EGT3"]
    for name in egt_names:
        others = [abs(z[x]) for x in egt_names if x != name]
        score = 100.0
        reason = "consistent with peer EGT channels"
        if abs(z[name]) > 4.0 and max(others) < 1.5:
            score = 35.0
            reason = "single-channel EGT deviation inconsistent with peer channels"
        elif abs(z[name]) > 3.0 and max(others) < 2.0:
            score = 60.0
            reason = "EGT channel deviates more than peer channels"
        results.append(SensorAssessment(name, score, _status(score), reason))

    # Cooling temperature drift check: if water temperature alone is extreme
    # while EGT and oil temperature remain close to reference, suspect sensing.
    avg_egt_abs = sum(abs(z[x]) for x in egt_names) / 3
    water_score = 100.0
    water_reason = "thermal channels are mutually consistent"
    if abs(z["EFI_Water_Temp"]) > 4.0 and avg_egt_abs < 1.5 and abs(z["Oil_Temp"]) < 1.5:
        water_score = 25.0
        water_reason = "water-temperature excursion is not supported by other thermal channels"
    elif abs(z["EFI_Water_Temp"]) > 3.0 and avg_egt_abs < 2.0:
        water_score = 55.0
        water_reason = "water-temperature deviation has weak corroboration"
    results.append(
        SensorAssessment(
            "EFI_Water_Temp",
            water_score,
            _status(water_score),
            water_reason,
        )
    )

    # Oil pressure should be interpreted together with oil temperature.
    oil_score = 100.0
    oil_reason = "oil pressure is consistent with lubrication state"
    if abs(z["Oil_Pressure"]) > 4.0 and abs(z["Oil_Temp"]) < 0.8:
        oil_score = 50.0
        oil_reason = "large oil-pressure deviation with little thermal corroboration"
    results.append(
        SensorAssessment("Oil_Pressure", oil_score, _status(oil_score), oil_reason)
    )

    assessments = [item.as_dict() for item in results]
    overall = min(item["trust_score"] for item in assessments)
    suspects = [item for item in assessments if item["status"] == "SUSPECT"]

    return {
        "overall_trust_score": round(_clamp(overall), 1),
        "overall_status": _status(overall),
        "suspected_sensor_fault": bool(suspects),
        "suspect_channels": [item["name"] for item in suspects],
        "channels": assessments,
        "note": "Prototype cross-sensor consistency logic; requires target-engine validation.",
    }

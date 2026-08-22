from __future__ import annotations

from .mission_whatif import MissionScenario, MissionWhatIf
from .rul_service import RULService


class MissionWhatIfRUL:
    """Compare mission scenarios by predicted engine RUL."""

    def __init__(self, degradation_rates: dict[str, float] | None = None):
        self.scenarios = MissionWhatIf(degradation_rates)
        self.rul = RULService()

    def run(self, telemetry: dict, scenario: MissionScenario) -> dict:
        result = self.scenarios.run(telemetry, scenario)
        rul = self.rul.predict(
            result["telemetry"],
            {"mission_hours": scenario.duration_h},
        )
        return {**result, "rul": rul}

    def compare(self, telemetry: dict, baseline: MissionScenario, alternative: MissionScenario) -> dict:
        base = self.run(telemetry, baseline)
        alt = self.run(telemetry, alternative)
        return {
            "baseline": base,
            "alternative": alt,
            "impact": {
                "rul_hours": round(alt["rul"]["rul_hours"] - base["rul"]["rul_hours"], 2),
                "rul_lower_hours": round(alt["rul"]["rul_lower_hours"] - base["rul"]["rul_lower_hours"], 2),
                "rul_upper_hours": round(alt["rul"]["rul_upper_hours"] - base["rul"]["rul_upper_hours"], 2),
                "health_index": round(alt["health_index"] - base["health_index"], 2),
                "degradation_severity": round(alt["degradation_severity"] - base["degradation_severity"], 4),
            },
        }

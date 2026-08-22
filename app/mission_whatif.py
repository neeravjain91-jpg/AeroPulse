from __future__ import annotations

from dataclasses import dataclass

from .rul_model import health_index
from .simulator import mission_adjust


@dataclass(frozen=True)
class MissionScenario:
    name: str
    altitude_ft: float = 3000.0
    ambient_c: float = 25.0
    duration_h: float = 4.0
    rapid_throttle: bool = False


class MissionWhatIf:
    """Run and compare mission scenarios through the existing engine pipeline."""

    def __init__(self, degradation_rates: dict[str, float] | None = None):
        self.degradation_rates = degradation_rates or {}

    def run(self, telemetry: dict, scenario: MissionScenario) -> dict:
        result = mission_adjust(
            telemetry,
            altitude_ft=scenario.altitude_ft,
            ambient_c=scenario.ambient_c,
            duration_h=scenario.duration_h,
            rapid_throttle=scenario.rapid_throttle,
            degradation_rates=self.degradation_rates,
        )
        return {
            "scenario": scenario.name,
            "altitude_ft": scenario.altitude_ft,
            "ambient_c": scenario.ambient_c,
            "duration_h": scenario.duration_h,
            "rapid_throttle": scenario.rapid_throttle,
            "health_index": round(health_index(result) * 100.0, 2),
            "degradation_severity": round(float(result["Degradation_Severity"]), 4),
            "engine_rpm": round(float(result["Engine_RPM"]), 2),
            "egt1": round(float(result["EGT1"]), 2),
            "cht": round(float(result["CHT"]), 2),
            "oil_pressure": round(float(result["Oil_Pressure"]), 2),
            "fuel_flow": round(float(result["Fuel_Flow"]), 2),
            "vibration": round(float(result["Vibration"]), 4),
            "efficiency": round(float(result["Efficiency"]), 4),
            "telemetry": result,
        }

    def compare(self, telemetry: dict, baseline: MissionScenario, alternative: MissionScenario) -> dict:
        base = self.run(telemetry, baseline)
        alt = self.run(telemetry, alternative)
        return {
            "baseline": base,
            "alternative": alt,
            "delta": {
                "health_index": round(alt["health_index"] - base["health_index"], 2),
                "degradation_severity": round(alt["degradation_severity"] - base["degradation_severity"], 4),
                "cht": round(alt["cht"] - base["cht"], 2),
                "oil_pressure": round(alt["oil_pressure"] - base["oil_pressure"], 2),
                "vibration": round(alt["vibration"] - base["vibration"], 4),
                "efficiency": round(alt["efficiency"] - base["efficiency"], 4),
            },
        }

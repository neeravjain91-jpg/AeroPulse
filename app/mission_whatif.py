"""Mission Scenario Models and What-If Simulation Engine."""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from .engine_model import EngineInputs, ReducedOrderPistonEngine
from .simulator import mission_adjust


@dataclass
class MissionScenario:
    """Defines operational profile and environmental envelope for a mission scenario."""
    name: str = "nominal"
    altitude_ft: float = 8000.0
    ambient_c: float = 35.0
    duration_h: float = 6.0
    rapid_throttle: bool = False
    operating_state: str = "CRUISE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MissionWhatIf:
    """
    Simulates engine response, degradation, and performance under varied mission scenarios.
    """

    def __init__(self, degradation_rates: Optional[dict[str, float]] = None):
        self.rates = degradation_rates or {
            "injector": 0.05,
            "lubrication": 0.04,
            "thermal": 0.03,
            "mechanical": 0.02,
            "electrical": 0.01,
            "sensor": 0.02,
        }
        self.engine_model = ReducedOrderPistonEngine()

    def run(self, telemetry: dict, scenario: MissionScenario) -> dict[str, Any]:
        data = copy.deepcopy(telemetry)

        # Apply mission environmental adjustment
        adjusted = mission_adjust(
            data,
            altitude_ft=scenario.altitude_ft,
            ambient_c=scenario.ambient_c,
            duration_h=scenario.duration_h,
            rapid_throttle=scenario.rapid_throttle,
        )

        # Calculate ISA air density ratio
        _, _, sigma = self.engine_model._isa_atmosphere(scenario.altitude_ft, scenario.ambient_c)
        adjusted["Air_Density_Ratio"] = round(sigma, 4)

        throttle = 0.75 if scenario.rapid_throttle else 0.60
        cht = float(adjusted.get("CHT", 180.0))
        fuel_flow = float(adjusted.get("Fuel_Flow", 25.0))
        vibration = float(adjusted.get("Vibration", 0.5)) + (0.2 if scenario.rapid_throttle else 0.0) + (scenario.altitude_ft / 100000.0)
        efficiency = float(adjusted.get("Efficiency", 0.65)) * (0.94 if scenario.rapid_throttle else 1.0) * math.sqrt(sigma)

        # Cumulative degradation severity
        thermal_rate = self.rates.get("thermal", 0.03) * max(0.0, (scenario.ambient_c - 20.0) / 25.0)
        alt_rate = self.rates.get("mechanical", 0.02) * (scenario.altitude_ft / 15000.0)
        duration_rate = max(0.0, scenario.duration_h - 2.0) * 0.04
        dynamic_rate = 0.15 if scenario.rapid_throttle else 0.0

        deg_severity = min(1.0, 0.05 + (thermal_rate + alt_rate + duration_rate + dynamic_rate))
        health_index = max(10.0, min(100.0, 100.0 - deg_severity * 60.0))

        adjusted["Vibration"] = round(vibration, 3)
        adjusted["Efficiency"] = round(efficiency, 4)
        adjusted["Degradation_Severity"] = round(deg_severity, 3)

        return {
            "scenario": scenario.name,
            "telemetry": adjusted,
            "cht": round(cht, 1),
            "fuel_flow": round(fuel_flow, 2),
            "vibration": round(vibration, 3),
            "efficiency": round(efficiency, 4),
            "degradation_severity": round(deg_severity, 3),
            "health_index": round(health_index, 1),
            "air_density_ratio": round(sigma, 4),
        }

    def compare(self, telemetry: dict, baseline: MissionScenario, alternative: MissionScenario) -> dict[str, Any]:
        base_eval = self.run(telemetry, baseline)
        alt_eval = self.run(telemetry, alternative)

        delta = {
            "health_index": round(alt_eval["health_index"] - base_eval["health_index"], 2),
            "vibration": round(alt_eval["vibration"] - base_eval["vibration"], 3),
            "fuel_flow": round(alt_eval["fuel_flow"] - base_eval["fuel_flow"], 2),
            "cht": round(alt_eval["cht"] - base_eval["cht"], 1),
            "efficiency": round(alt_eval["efficiency"] - base_eval["efficiency"], 4),
            "degradation_severity": round(alt_eval["degradation_severity"] - base_eval["degradation_severity"], 3),
        }

        return {
            "baseline": base_eval,
            "alternative": alt_eval,
            "delta": delta,
        }

"""What-If Mission Scenario and Comparative RUL Impact Engine."""
from __future__ import annotations

import math
from typing import Any, Dict, Optional

from .engine_model import EngineInputs, ReducedOrderPistonEngine
from .mission_whatif import MissionScenario
from .rul_service import RULService
from .simulator import mission_adjust


class MissionWhatIfRUL:
    """
    Simulates and compares the degradation impact and Remaining Useful Life (RUL)
    of alternative mission flight profiles against a baseline flight plan.
    """

    def __init__(self, degradation_weights: Optional[dict[str, float]] = None):
        self.weights = degradation_weights or {
            "injector": 0.05,
            "lubrication": 0.04,
            "thermal": 0.03,
            "mechanical": 0.02,
            "electrical": 0.01,
            "sensor": 0.02,
        }
        self.engine = ReducedOrderPistonEngine()
        self.rul_service = RULService()

    def evaluate_scenario(self, base_telemetry: dict, scenario: MissionScenario) -> dict[str, Any]:
        """Evaluates engine response and projected health/RUL under a single mission scenario."""
        sim_telemetry = mission_adjust(
            base_telemetry,
            altitude_ft=scenario.altitude_ft,
            ambient_c=scenario.ambient_c,
            duration_h=scenario.duration_h,
            rapid_throttle=scenario.rapid_throttle,
        )

        stress = self.rul_service.calculate_mission_stress(scenario.to_dict())

        # Physical engine state from thermodynamic model
        eng_inputs = EngineInputs(
            rpm=float(sim_telemetry.get("Engine_RPM", 3000.0)),
            throttle=0.75 if scenario.rapid_throttle else 0.60,
            altitude_ft=scenario.altitude_ft,
            ambient_c=scenario.ambient_c,
        )
        phys_state = self.engine.estimate_state(eng_inputs)

        # Thermal stress factor
        cht = float(sim_telemetry.get("CHT", 220.0))
        oil_temp = float(sim_telemetry.get("Oil_Temp", 90.0))
        egt_avg = (
            float(sim_telemetry.get("EGT1", 1200.0))
            + float(sim_telemetry.get("EGT2", 1200.0))
            + float(sim_telemetry.get("EGT3", 1200.0))
        ) / 3.0

        thermal_severity = max(0.0, (cht - 210.0) / 100.0) + max(0.0, (oil_temp - 95.0) / 30.0)

        # Health degradation rate (% per hour)
        base_health_loss_per_h = (0.045 + 0.03 * thermal_severity) * stress
        cumulative_mission_health_loss = base_health_loss_per_h * scenario.duration_h

        projected_health_end_of_mission = max(20.0, 100.0 - cumulative_mission_health_loss)

        rul_res = self.rul_service.estimate_rul(
            health_index=projected_health_end_of_mission,
            context=scenario.to_dict(),
        )

        fuel_rate_l_h = float(sim_telemetry.get("Fuel_Flow", 20.0))
        total_mission_fuel_l = fuel_rate_l_h * scenario.duration_h

        return {
            "scenario": scenario.to_dict(),
            "stress_multiplier": stress,
            "thermal_severity_index": round(thermal_severity, 3),
            "projected_final_health_index": round(projected_health_end_of_mission, 2),
            "mission_health_loss": round(cumulative_mission_health_loss, 2),
            "degradation_rate_per_hour": round(base_health_loss_per_h, 3),
            "rul_hours": rul_res["rul_hours"],
            "rul_lower_hours": rul_res["rul_lower_hours"],
            "rul_upper_hours": rul_res["rul_upper_hours"],
            "rul_confidence": rul_res["confidence"],
            "fuel_flow_l_h": round(fuel_rate_l_h, 2),
            "total_fuel_burn_l": round(total_mission_fuel_l, 1),
            "thermal_telemetry": {
                "CHT": round(cht, 1),
                "Oil_Temp": round(oil_temp, 1),
                "EGT_Avg": round(egt_avg, 1),
            },
            "indicated_power_kw": phys_state.indicated_power_kw,
            "brake_power_kw": phys_state.brake_power_kw,
            "volumetric_efficiency": phys_state.volumetric_efficiency,
        }

    def compare(
        self,
        base_telemetry: dict,
        baseline_scenario: MissionScenario,
        alternative_scenario: MissionScenario,
    ) -> dict[str, Any]:
        """Compares baseline vs alternative mission profile."""
        base_eval = self.evaluate_scenario(base_telemetry, baseline_scenario)
        alt_eval = self.evaluate_scenario(base_telemetry, alternative_scenario)

        rul_delta = (alt_eval["rul_hours"] or 0.0) - (base_eval["rul_hours"] or 0.0)
        fuel_delta = alt_eval["total_fuel_burn_l"] - base_eval["total_fuel_burn_l"]
        fuel_pct = (
            (fuel_delta / max(base_eval["total_fuel_burn_l"], 1e-6)) * 100.0
            if base_eval["total_fuel_burn_l"] > 0
            else 0.0
        )
        stress_delta = alt_eval["stress_multiplier"] - base_eval["stress_multiplier"]

        if rul_delta >= 0:
            recommendation = (
                f"Alternative profile extends projected engine RUL by +{rul_delta:.1f} hours "
                f"(Fuel delta: {fuel_delta:+.1f} L / {fuel_pct:+.1f}%)."
            )
            risk_assessment = "FAVORABLE_OR_CONSERVATIVE"
        else:
            recommendation = (
                f"Alternative profile incurs elevated stress, reducing projected RUL by {abs(rul_delta):.1f} hours "
                f"(Fuel delta: {fuel_delta:+.1f} L / {fuel_pct:+.1f}%)."
            )
            risk_assessment = "ELEVATED_THERMOMECHANICAL_PENALTY"

        return {
            "baseline": base_eval,
            "alternative": alt_eval,
            "comparison": {
                "rul_delta_hours": round(rul_delta, 2),
                "fuel_delta_liters": round(fuel_delta, 2),
                "fuel_delta_percent": round(fuel_pct, 2),
                "stress_multiplier_delta": round(stress_delta, 3),
                "recommendation": recommendation,
                "risk_assessment": risk_assessment,
            },
        }

"""Remaining Useful Life (RUL) and Prognostics Analytics Service for Aero Piston Engines."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np

from .degradation import estimate_degradation_horizon


@dataclass
class RULPrediction:
    rul_hours: Optional[float]
    rul_lower_hours: Optional[float]
    rul_upper_hours: Optional[float]
    confidence: float
    degradation_rate_per_hour: float
    status: str
    failure_mode_risk: str
    stress_multiplier: float
    method: str


class RULService:
    """
    Predictive RUL and Prognostic Analytics engine for UAV aero-piston engines.
    """

    CRITICAL_HEALTH_THRESHOLD: float = 35.0
    WARNING_HEALTH_THRESHOLD: float = 60.0
    NOMINAL_TBO_HOURS: float = 2000.0

    def __init__(self):
        self.weibull_beta: float = 2.4
        self.weibull_eta: float = 2200.0

    def calculate_mission_stress(self, context: Optional[dict] = None) -> float:
        if not context:
            return 1.0

        altitude_ft = float(context.get("altitude_ft", 3000.0))
        ambient_c = float(context.get("ambient_c", 25.0))
        duration_h = float(context.get("duration_h", 4.0))
        rapid_throttle = bool(context.get("rapid_throttle", False))
        throttle = float(context.get("throttle", 0.60))

        alt_stress = 1.0 + 0.35 * max(0.0, (altitude_ft - 10000.0) / 15000.0)
        thermal_stress = 1.0 + 0.40 * max(0.0, (ambient_c - 25.0) / 25.0)
        endurance_stress = 1.0 + 0.20 * max(0.0, (duration_h - 6.0) / 12.0)
        dynamic_stress = 1.35 if rapid_throttle else (1.0 + 0.15 * max(0.0, (throttle - 0.70) / 0.30))

        cumulative_stress = alt_stress * thermal_stress * endurance_stress * dynamic_stress
        return round(max(0.8, min(3.5, cumulative_stress)), 3)

    def estimate_rul(
        self,
        health_index: float,
        health_history: Optional[List[float]] = None,
        context: Optional[dict] = None,
        step_minutes: float = 5.0,
    ) -> dict[str, Any]:
        current_health = max(0.0, min(100.0, float(health_index)))
        stress = self.calculate_mission_stress(context)

        if health_history and len(health_history) >= 6:
            trend_res = estimate_degradation_horizon(
                health_history,
                step_minutes=step_minutes,
                critical_health_index=self.CRITICAL_HEALTH_THRESHOLD,
            )

            if trend_res.get("rul_hours") is not None and trend_res.get("status") == "DEGRADING":
                base_rul = float(trend_res["rul_hours"])
                adjusted_rul = max(0.5, base_rul / math.sqrt(stress))
                confidence = float(trend_res.get("confidence", 0.75))
                spread = (1.0 - confidence) * 0.35

                return {
                    "rul_hours": round(adjusted_rul, 2),
                    "rul_lower_hours": max(0.0, round(adjusted_rul * (1.0 - spread), 2)),
                    "rul_upper_hours": round(adjusted_rul * (1.0 + spread), 2),
                    "confidence": round(confidence, 2),
                    "rul_confidence": round(confidence, 2),
                    "degradation_rate_per_hour": round(float(trend_res.get("trend_per_hour", 0.5)), 3),
                    "status": "ACTIVE_DEGRADATION",
                    "failure_mode_risk": self._diagnose_risk_tier(current_health),
                    "stress_multiplier": stress,
                    "method": "Physics-Stress Weighted Trend Extrapolation",
                }

        nominal_deg_rate = 0.045 * stress

        if current_health <= self.CRITICAL_HEALTH_THRESHOLD:
            rul_h = 0.0
            rul_lower = 0.0
            rul_upper = 1.0
            confidence = 0.95
            status = "CRITICAL_MAINTENANCE_REQUIRED"
        elif current_health <= self.WARNING_HEALTH_THRESHOLD:
            remaining_points = current_health - self.CRITICAL_HEALTH_THRESHOLD
            rul_h = remaining_points / max(nominal_deg_rate * 2.5, 0.05)
            confidence = 0.80
            spread = 0.25
            rul_lower = rul_h * (1.0 - spread)
            rul_upper = rul_h * (1.0 + spread)
            status = "WARNING_ELEVATED_WEAR"
        else:
            remaining_points = current_health - self.CRITICAL_HEALTH_THRESHOLD
            rul_h = remaining_points / max(nominal_deg_rate, 0.02)
            rul_h = min(self.NOMINAL_TBO_HOURS, rul_h)
            confidence = 0.70
            spread = 0.30
            rul_lower = rul_h * (1.0 - spread)
            rul_upper = rul_h * (1.0 + spread)
            status = "NOMINAL_HEALTH"

        return {
            "rul_hours": round(rul_h, 2),
            "rul_lower_hours": max(0.0, round(rul_lower, 2)),
            "rul_upper_hours": round(rul_upper, 2),
            "confidence": round(confidence, 2),
            "rul_confidence": round(confidence, 2),
            "degradation_rate_per_hour": round(nominal_deg_rate, 3),
            "status": status,
            "failure_mode_risk": self._diagnose_risk_tier(current_health),
            "stress_multiplier": stress,
            "method": "Hybrid Physics-Weibull Model",
        }

    def predict(
        self,
        telemetry: dict,
        context: Optional[dict] = None,
        health_history: Optional[List[float]] = None,
    ) -> dict[str, Any]:
        """Inference interface for live pipeline."""
        context = context or {}
        deg_sev = float(telemetry.get("Degradation_Severity", 0.0))
        base_health = max(10.0, 100.0 - deg_sev * 60.0)

        slope = context.get("degradation_slope")
        if slope is not None:
            slope_val = float(slope)
            remaining = base_health - self.CRITICAL_HEALTH_THRESHOLD
            divisor = abs(slope_val * 60.0) if abs(slope_val) < 0.2 else abs(slope_val)
            rul_val = max(0.0, remaining / max(0.01, divisor))
            return {
                "rul_hours": round(rul_val, 2),
                "rul_lower_hours": max(0.0, round(rul_val * 0.75, 2)),
                "rul_upper_hours": round(rul_val * 1.25, 2),
                "confidence": 0.85,
                "rul_confidence": 0.85,
                "health_index_for_rul": round(base_health, 1),
                "degradation_slope": slope_val,
                "degradation_severity": round(deg_sev, 3),
                "status": "SLOPE_EXTRAPOLATED",
                "failure_mode_risk": self._diagnose_risk_tier(base_health),
                "stress_multiplier": 1.0,
                "method": "Explicit Slope Estimation",
            }

        res = self.estimate_rul(
            health_index=base_health,
            health_history=health_history,
            context=context,
        )
        res["health_index_for_rul"] = round(base_health, 1)
        res["degradation_severity"] = round(deg_sev, 3)
        res["degradation_slope"] = round(-res.get("degradation_rate_per_hour", 0.05) / 60.0, 4)
        return res

    @staticmethod
    def _diagnose_risk_tier(health: float) -> str:
        if health < 35.0:
            return "IMMINENT_IN_FLIGHT_ABORT_RISK"
        if health < 55.0:
            return "ACCELERATED_SUBSYSTEM_WEAR"
        if health < 75.0:
            return "MODERATE_THERMOMECHANICAL_STRESS"
        return "LOW_OPERATIONAL_RISK"

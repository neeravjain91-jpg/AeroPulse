from __future__ import annotations

from .rul_model import RULModel, generate_training_trajectories, health_index


class RULService:
    """Lazy-loaded RUL service for inference-time health prediction."""

    def __init__(self):
        health, slope, severity, rul = generate_training_trajectories(n_trajectories=80, seed=42)
        self.model = RULModel().fit(health, slope, severity, rul)

    @staticmethod
    def _slope_from_context(telemetry: dict, context: dict | None) -> float:
        if context and "degradation_slope" in context:
            return float(context["degradation_slope"])
        severity = float(telemetry.get("Degradation_Severity", 0.0))
        duration = max(float((context or {}).get("mission_hours", 1.0)), 1e-6)
        return -severity / duration

    def predict(self, telemetry: dict, context: dict | None = None):
        health = health_index(telemetry)
        severity = float(telemetry.get("Degradation_Severity", 0.0))
        slope = self._slope_from_context(telemetry, context)
        prediction = self.model.predict(health, slope, severity)
        return {
            "rul_hours": round(prediction.rul_hours, 2),
            "rul_lower_hours": round(prediction.lower_hours, 2),
            "rul_upper_hours": round(prediction.upper_hours, 2),
            "rul_confidence": round(prediction.confidence, 4),
            "health_index_for_rul": round(health, 4),
            "degradation_severity": round(severity, 4),
            "degradation_slope": round(slope, 6),
        }

from __future__ import annotations

import json
import math

from .config import MODEL_DIR
from .engine_model import EngineInputs, ReducedOrderPistonEngine

PARAMS = [
    "Engine_RPM", "EGT1", "EGT2", "EGT3", "CHT", "Fuel_Flow",
    "Oil_Temp", "Oil_Pressure", "Battery_Voltage", "Battery_Current",
    "Alternator_Temp", "EFI_Fuel_Temp", "EFI_Water_Temp", "MAP_Injector",
]

ENGINE_MODEL_MAP = {
    "Engine_RPM": "Engine_RPM", "EGT1": "EGT1", "EGT2": "EGT2", "EGT3": "EGT3",
    "CHT": "CHT", "Fuel_Flow": "Fuel_Flow", "Oil_Temp": "Oil_Temp",
    "Oil_Pressure": "Oil_Pressure", "Battery_Voltage": "Battery_Voltage",
    "Battery_Current": "Battery_Current", "Alternator_Temp": "Alternator_Temp",
    "EFI_Fuel_Temp": "EFI_Fuel_Temp", "EFI_Water_Temp": "EFI_Water_Temp",
    "MAP_Injector": "MAP_Injector",
}


class ReferenceTwin:
    """Hybrid prototype Twin: statistical ACES reference + reduced-order engine model."""

    def __init__(self):
        self.stats = json.loads((MODEL_DIR / "healthy_reference.json").read_text())
        self.engine_model = ReducedOrderPistonEngine()

    @property
    def operating_states(self) -> list[str]:
        return sorted(key for key in self.stats if key != "_GLOBAL_")

    def expected(self, operating_state: str):
        state = self.stats.get(str(operating_state), self.stats["_GLOBAL_"])
        return {key: value["median"] for key, value in state.items()}

    def _contextual_expected(self, ref: dict, context: dict | None) -> dict:
        expected = {parameter: float(ref[parameter]["median"]) for parameter in PARAMS}
        if not context:
            return expected
        altitude_factor = max(0.0, float(context.get("altitude_ft", 3000))) / 10000
        hot_factor = max(0.0, float(context.get("ambient_c", 25)) - 25) / 25
        endurance_factor = max(0.0, float(context.get("duration_h", 4)) - 4) / 8
        expected["MAP_Injector"] *= 1 + 0.08 * altitude_factor
        for key in ["EGT1", "EGT2", "EGT3"]:
            expected[key] *= 1 + 0.025 * altitude_factor + 0.035 * hot_factor + 0.02 * endurance_factor
        expected["Oil_Temp"] *= 1 + 0.02 * hot_factor + 0.02 * endurance_factor
        expected["EFI_Water_Temp"] *= 1 + 0.025 * hot_factor + 0.015 * endurance_factor
        expected["CHT"] *= 1 + 0.02 * altitude_factor + 0.04 * hot_factor + 0.02 * endurance_factor
        expected["Alternator_Temp"] *= 1 + 0.015 * hot_factor + 0.01 * endurance_factor
        if bool(context.get("rapid_throttle", False)):
            expected["Engine_RPM"] *= 1.04
            expected["Fuel_Flow"] *= 1.08
        return expected

    def _physics_expected(self, ref: dict, context: dict | None) -> dict:
        """Generate physics-informed expected values while preserving ACES units.

        The reduced-order model is calibrated to the healthy-reference medians at
        the reference operating point. Its relative response to mission conditions
        is then applied to those medians. This avoids treating the demonstrator's
        arbitrary physical units as measured ACES sensor units.
        """
        context = context or {}
        rpm = float(context.get("rpm", context.get("Engine_RPM", 3000.0)))
        throttle = float(context.get("throttle", 0.60))
        altitude = float(context.get("altitude_ft", 3000.0))
        ambient = float(context.get("ambient_c", 25.0))
        load = context.get("load")

        current = self.engine_model.predict(EngineInputs(
            rpm=rpm, throttle=throttle, altitude_ft=altitude,
            ambient_c=ambient, load=load,
        ))
        reference = self.engine_model.predict(EngineInputs(
            rpm=3000.0, throttle=0.60, altitude_ft=3000.0,
            ambient_c=25.0, load=None,
        ))

        physics_expected = {}
        for parameter in PARAMS:
            model_key = ENGINE_MODEL_MAP[parameter]
            ref_model = max(abs(float(reference[model_key])), 1e-9)
            ratio = float(current[model_key]) / ref_model
            physics_expected[parameter] = float(ref[parameter]["median"]) * ratio
        return physics_expected

    def compare(self, telemetry: dict, context: dict | None = None):
        state = str(telemetry.get("Operating_State", "_GLOBAL_"))
        ref = self.stats.get(state, self.stats["_GLOBAL_"])
        expected = self._contextual_expected(ref, context)
        physics_expected = self._physics_expected(ref, context)

        # Blend the empirical ACES reference and physics-informed response.
        # ACES remains the measurement-domain anchor; the engine model supplies
        # physically structured changes for mission conditions.
        expected = {
            parameter: 0.70 * float(expected[parameter]) + 0.30 * float(physics_expected[parameter])
            for parameter in PARAMS
        }

        residuals, z_scores, percentage_deviation = {}, {}, {}
        for parameter in PARAMS:
            observed = float(telemetry[parameter])
            median = float(expected[parameter])
            std = max(float(ref[parameter]["std"]), 1e-6)
            residual = observed - median
            residuals[parameter] = residual
            z_scores[parameter] = residual / std
            percentage_deviation[parameter] = 100.0 * residual / abs(median) if abs(median) > 1e-9 else 0.0

        max_abs_z = max(abs(value) for value in z_scores.values())
        residual_rms = math.sqrt(sum(value * value for value in z_scores.values()) / len(z_scores))
        dominant = sorted(({
            "parameter": parameter,
            "z_score": round(float(z_scores[parameter]), 3),
            "residual": round(float(residuals[parameter]), 3),
            "percentage_deviation": round(float(percentage_deviation[parameter]), 2),
        } for parameter in PARAMS), key=lambda item: abs(item["z_score"]), reverse=True)[:5]
        return {
            "operating_state": state, "expected": expected, "physics_expected": physics_expected,
            "residuals": residuals, "z_scores": z_scores, "percentage_deviation": percentage_deviation,
            "residual_rms": residual_rms, "max_abs_z": max_abs_z,
            "dominant_deviations": dominant, "reference_alarm": max_abs_z >= 3.0,
            "reference_note": "Hybrid healthy-reference Twin: ACES operating-state statistics blended with a calibrated reduced-order engine model for mission-context response.",
        }

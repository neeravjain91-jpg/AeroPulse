from __future__ import annotations

import json
import math

from .config import MODEL_DIR

PARAMS = [
    "Engine_RPM", "EGT1", "EGT2", "EGT3", "CHT", "Fuel_Flow",
    "Oil_Temp", "Oil_Pressure", "Battery_Voltage", "Battery_Current",
    "Alternator_Temp", "EFI_Fuel_Temp", "EFI_Water_Temp", "MAP_Injector",
]


class ReferenceTwin:
    """Healthy-reference Digital Twin built from operating-state statistics."""

    def __init__(self):
        self.stats = json.loads((MODEL_DIR / "healthy_reference.json").read_text())

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

    def compare(self, telemetry: dict, context: dict | None = None):
        state = str(telemetry.get("Operating_State", "_GLOBAL_"))
        ref = self.stats.get(state, self.stats["_GLOBAL_"])
        expected = self._contextual_expected(ref, context)
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
            "operating_state": state, "expected": expected, "residuals": residuals,
            "z_scores": z_scores, "percentage_deviation": percentage_deviation,
            "residual_rms": residual_rms, "max_abs_z": max_abs_z,
            "dominant_deviations": dominant, "reference_alarm": max_abs_z >= 3.0,
            "reference_note": "Healthy-reference statistics learned from ACES Normal samples by operating state and context-adjusted for the prototype mission scenario.",
        }

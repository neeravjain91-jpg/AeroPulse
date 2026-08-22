from __future__ import annotations

import json
import math

from .config import MODEL_DIR

PARAMS = [
    "Engine_RPM",
    "EGT1",
    "EGT2",
    "EGT3",
    "Fuel_Flow",
    "Oil_Temp",
    "Oil_Pressure",
    "EFI_Fuel_Temp",
    "EFI_Water_Temp",
    "MAP_Injector",
]


class ReferenceTwin:
    def __init__(self):
        self.stats = json.loads((MODEL_DIR / "healthy_reference.json").read_text())

    def expected(self, operating_state: str):
        state = self.stats.get(operating_state, self.stats["_GLOBAL_"])
        return {key: value["median"] for key, value in state.items()}

    def compare(self, telemetry: dict):
        state = str(telemetry.get("Operating_State", "_GLOBAL_"))
        ref = self.stats.get(state, self.stats["_GLOBAL_"])

        residuals = {}
        z_scores = {}
        for parameter in PARAMS:
            observed = float(telemetry[parameter])
            median = ref[parameter]["median"]
            std = max(ref[parameter]["std"], 1e-6)
            residuals[parameter] = observed - median
            z_scores[parameter] = (observed - median) / std

        max_abs_z = max(abs(value) for value in z_scores.values())
        residual_rms = math.sqrt(
            sum(value * value for value in z_scores.values()) / len(z_scores)
        )

        return {
            "expected": {parameter: ref[parameter]["median"] for parameter in PARAMS},
            "residuals": residuals,
            "z_scores": z_scores,
            "residual_rms": residual_rms,
            "max_abs_z": max_abs_z,
        }

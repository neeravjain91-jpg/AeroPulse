from __future__ import annotations

import copy

FAULTS = {"none", "overheating", "lubrication", "misfire", "injector", "sensor_drift"}


def inject_fault(telemetry: dict, fault: str = "none", severity: float = 0.6):
    data = copy.deepcopy(telemetry)
    strength = max(0.0, min(1.0, float(severity)))

    if fault == "overheating":
        for key in ["EGT1", "EGT2", "EGT3"]:
            data[key] *= 1 + 0.10 + 0.22 * strength
        data["EFI_Water_Temp"] *= 1 + 0.08 + 0.18 * strength
        data["Oil_Temp"] *= 1 + 0.05 + 0.12 * strength

    elif fault == "lubrication":
        data["Oil_Pressure"] *= max(0.25, 1 - (0.20 + 0.45 * strength))
        data["Oil_Temp"] *= 1 + 0.06 + 0.20 * strength

    elif fault == "misfire":
        data["Engine_RPM"] *= 1 - (0.02 + 0.06 * strength)
        data["EGT1"] *= 1 - (0.08 + 0.18 * strength)
        data["EGT2"] *= 1 + 0.03 * strength

    elif fault == "injector":
        data["Fuel_Flow"] *= 1 - (0.08 + 0.25 * strength)
        data["MAP_Injector"] *= 1 + (0.10 + 0.35 * strength)
        data["EGT3"] *= 1 - (0.05 + 0.15 * strength)

    elif fault == "sensor_drift":
        data["EFI_Water_Temp"] += 25 + 50 * strength

    return data


def mission_adjust(
    telemetry: dict,
    altitude_ft: float = 3000,
    ambient_c: float = 25,
    duration_h: float = 4,
    rapid_throttle: bool = False,
):
    data = copy.deepcopy(telemetry)
    altitude_factor = max(0.0, altitude_ft) / 10000
    hot_factor = max(0.0, ambient_c - 25) / 25
    endurance_factor = max(0.0, duration_h - 4) / 8

    # Demonstrator response functions only. Replace with validated engine maps when available.
    data["MAP_Injector"] *= 1 + 0.08 * altitude_factor
    for key in ["EGT1", "EGT2", "EGT3"]:
        data[key] *= 1 + 0.025 * altitude_factor + 0.035 * hot_factor + 0.02 * endurance_factor
    data["Oil_Temp"] *= 1 + 0.02 * hot_factor + 0.02 * endurance_factor
    data["EFI_Water_Temp"] *= 1 + 0.025 * hot_factor + 0.015 * endurance_factor

    if rapid_throttle:
        data["Engine_RPM"] *= 1.04
        data["Fuel_Flow"] *= 1.08

    return data

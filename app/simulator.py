"""Simulator for UAV mission conditions, fault injection, and degradation kinetics."""
from __future__ import annotations

import copy
import math
from typing import Any, Dict, Optional

FAULTS = {"none", "overheating", "lubrication", "misfire", "injector", "sensor_drift", "electrical"}


def inject_fault(telemetry: dict, fault: str = "none", severity: float = 0.6):
    data = copy.deepcopy(telemetry)
    fault = str(fault).lower()
    if fault not in FAULTS:
        raise ValueError(f"Unsupported fault '{fault}'. Allowed: {sorted(FAULTS)}")
    strength = max(0.0, min(1.0, float(severity)))

    if fault == "overheating":
        for key in ["EGT1", "EGT2", "EGT3"]:
            if key in data:
                data[key] *= 1 + 0.30 * strength
        if "EFI_Water_Temp" in data:
            data["EFI_Water_Temp"] *= 1 + 0.24 * strength
        if "Oil_Temp" in data:
            data["Oil_Temp"] *= 1 + 0.18 * strength
        if "CHT" in data:
            data["CHT"] *= 1 + 0.26 * strength

    elif fault == "lubrication":
        if "Oil_Pressure" in data:
            data["Oil_Pressure"] *= max(0.25, 1 - 0.65 * strength)
        if "Oil_Temp" in data:
            data["Oil_Temp"] *= 1 + 0.28 * strength

    elif fault == "misfire":
        if "Engine_RPM" in data:
            data["Engine_RPM"] *= 1 - 0.09 * strength
        if "EGT1" in data:
            data["EGT1"] *= 1 - 0.25 * strength
        if "EGT2" in data:
            data["EGT2"] *= 1 + 0.03 * strength

    elif fault == "injector":
        if "Fuel_Flow" in data:
            data["Fuel_Flow"] *= 1 - 0.32 * strength
        if "MAP_Injector" in data:
            data["MAP_Injector"] *= 1 + 0.45 * strength
        if "EGT3" in data:
            data["EGT3"] *= 1 - 0.20 * strength

    elif fault == "sensor_drift":
        if "EFI_Water_Temp" in data:
            data["EFI_Water_Temp"] += 75 * strength

    elif fault == "electrical":
        if "Battery_Voltage" in data:
            data["Battery_Voltage"] *= max(0.55, 1 - 0.30 * strength)
        if "Battery_Current" in data:
            data["Battery_Current"] -= 30 * strength
        if "Alternator_Temp" in data:
            data["Alternator_Temp"] *= 1 + 0.24 * strength

    return data


def mission_adjust(
    telemetry: dict,
    altitude_ft: float = 3000,
    ambient_c: float = 25,
    duration_h: float = 4,
    rapid_throttle: bool = False,
    degradation_rates: Optional[dict[str, float]] = None,
):
    data = copy.deepcopy(telemetry)
    alt_ft = max(0.0, float(altitude_ft))
    amb_c = float(ambient_c)
    dur_h = max(0.0, float(duration_h))

    # Standard ISA Barometric calculation
    h_m = alt_ft * 0.3048
    t_amb_k = 273.15 + amb_c - 0.0065 * h_m
    p_amb_ratio = math.pow(max(0.1, t_amb_k / (273.15 + amb_c)), 5.255)
    sigma = max(0.20, min(1.15, p_amb_ratio * ((273.15 + amb_c) / max(100.0, t_amb_k))))

    altitude_factor = alt_ft / 10000.0
    hot_factor = max(0.0, amb_c - 25.0) / 25.0
    endurance_factor = max(0.0, dur_h - 4.0) / 8.0

    # Base adjustments
    if "MAP_Injector" in data:
        # At high altitude, intake MAP drops with ambient density
        data["MAP_Injector"] = float(data["MAP_Injector"]) * (0.45 + 0.55 * sigma)

    for key in ["EGT1", "EGT2", "EGT3"]:
        if key in data:
            data[key] = float(data[key]) * (1.0 + 0.025 * altitude_factor + 0.035 * hot_factor + 0.02 * endurance_factor)

    if "Oil_Temp" in data:
        data["Oil_Temp"] = float(data["Oil_Temp"]) * (1.0 + 0.03 * hot_factor + 0.02 * endurance_factor)

    if "EFI_Water_Temp" in data:
        data["EFI_Water_Temp"] = float(data["EFI_Water_Temp"]) * (1.0 + 0.025 * hot_factor + 0.015 * endurance_factor)

    if "CHT" in data:
        data["CHT"] = float(data["CHT"]) * (1.0 + 0.02 * altitude_factor + 0.04 * hot_factor + 0.02 * endurance_factor)

    if "Alternator_Temp" in data:
        data["Alternator_Temp"] = float(data["Alternator_Temp"]) * (1.0 + 0.015 * hot_factor + 0.01 * endurance_factor)

    base_load = 0.90 if rapid_throttle else 0.70
    data["Load"] = round(base_load + 0.10 * hot_factor, 3)
    data["Air_Density_Ratio"] = round(sigma, 4)

    if "Fuel_Flow" in data:
        # High altitude lean mixture adjustment or throttle demand
        ff_mult = 1.15 if rapid_throttle else (1.0 + 0.04 * altitude_factor)
        data["Fuel_Flow"] = float(data["Fuel_Flow"]) * ff_mult

    if "Engine_RPM" in data and rapid_throttle:
        data["Engine_RPM"] = float(data["Engine_RPM"]) * 1.04

    # Dynamic vibration and efficiency
    base_vib = float(data.get("Vibration", 0.5))
    base_eff = float(data.get("Efficiency", 0.65))

    vib_calc = base_vib * (1.25 if rapid_throttle else 1.0) * (1.0 + 0.05 * altitude_factor)
    eff_calc = base_eff * (0.92 if rapid_throttle else 1.0) * math.sqrt(sigma)

    # Process degradation rates if supplied
    deg_state = {}
    total_sev = 0.0

    if degradation_rates is not None:
        for mode, rate in degradation_rates.items():
            mode_sev = float(rate) * dur_h
            deg_state[mode] = round(mode_sev, 4)
            total_sev += mode_sev

        deg_severity = round(min(1.0, total_sev), 4)
        data["Degradation_State"] = deg_state
        data["Degradation_Severity"] = deg_severity

        # Apply degradation consequences to physical outputs
        if "Oil_Pressure" in data and deg_severity > 0:
            data["Oil_Pressure"] = max(20.0, float(data["Oil_Pressure"]) * (1.0 - 0.25 * deg_severity))

        if deg_severity > 0:
            vib_calc *= (1.0 + 0.40 * deg_severity)
            if "CHT" in data:
                data["CHT"] = float(data["CHT"]) * (1.0 + 0.15 * deg_severity)

    data["Vibration"] = round(vib_calc, 3)
    data["Efficiency"] = round(eff_calc, 4)

    return data

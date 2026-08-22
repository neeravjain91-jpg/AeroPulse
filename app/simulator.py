from __future__ import annotations

import copy

from .engine_model import ReducedOrderPistonEngine

FAULTS = {"none", "overheating", "lubrication", "misfire", "injector", "sensor_drift", "electrical"}

_ENGINE = ReducedOrderPistonEngine()


def inject_fault(telemetry: dict, fault: str = "none", severity: float = 0.6):
    data = copy.deepcopy(telemetry); fault = str(fault).lower()
    if fault not in FAULTS: raise ValueError(f"Unsupported fault '{fault}'. Allowed: {sorted(FAULTS)}")
    strength = max(0.0, min(1.0, float(severity)))
    if fault == "overheating":
        for key in ["EGT1", "EGT2", "EGT3"]: data[key] *= 1 + 0.30 * strength
        data["EFI_Water_Temp"] *= 1 + 0.24 * strength; data["Oil_Temp"] *= 1 + 0.18 * strength; data["CHT"] *= 1 + 0.26 * strength
    elif fault == "lubrication":
        data["Oil_Pressure"] *= max(0.25, 1 - 0.65 * strength); data["Oil_Temp"] *= 1 + 0.28 * strength
    elif fault == "misfire":
        data["Engine_RPM"] *= 1 - 0.09 * strength; data["EGT1"] *= 1 - 0.25 * strength; data["EGT2"] *= 1 + 0.03 * strength
    elif fault == "injector":
        data["Fuel_Flow"] *= 1 - 0.32 * strength; data["MAP_Injector"] *= 1 + 0.45 * strength; data["EGT3"] *= 1 - 0.20 * strength
    elif fault == "sensor_drift": data["EFI_Water_Temp"] += 75 * strength
    elif fault == "electrical":
        data["Battery_Voltage"] *= max(0.55, 1 - 0.30 * strength); data["Battery_Current"] -= 30 * strength; data["Alternator_Temp"] *= 1 + 0.24 * strength
    return data


def mission_adjust(telemetry: dict, altitude_ft: float = 3000, ambient_c: float = 25, duration_h: float = 4, rapid_throttle: bool = False):
    """Generate mission-conditioned telemetry through the reduced-order engine model.

    Existing telemetry values are retained as the operating reference, while the
    engine model supplies the causal mission response. This keeps the legacy replay
    interface compatible with the existing ACES-derived baseline.
    """
    data = copy.deepcopy(telemetry)
    rpm = float(data.get("Engine_RPM", 3000.0))
    fuel_flow = float(data.get("Fuel_Flow", 0.0))
    throttle = 0.72 if fuel_flow <= 0 else max(0.0, min(1.0, fuel_flow / max(fuel_flow, 1e-9)))
    load = None
    if rapid_throttle:
        throttle = min(1.0, throttle + 0.08)

    model = _ENGINE.simulate(
        rpm=rpm,
        throttle=throttle,
        altitude_ft=altitude_ft,
        ambient_c=ambient_c,
        load=load,
    )

    # Blend the model response with the observed/reference baseline. The model
    # provides physically coupled directionality without replacing the calibrated
    # ACES telemetry distribution used by the rest of the prototype.
    for key in [
        "Engine_RPM", "EGT1", "EGT2", "EGT3", "CHT", "Fuel_Flow",
        "Oil_Temp", "Oil_Pressure", "EFI_Water_Temp", "MAP_Injector",
        "Alternator_Temp",
    ]:
        if key in model and key in data:
            data[key] = 0.5 * float(data[key]) + 0.5 * float(model[key])

    for key in ["Load", "Air_Density_Ratio", "Vibration", "Efficiency"]:
        if key in model:
            data[key] = float(model[key])
    return data

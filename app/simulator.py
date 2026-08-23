from __future__ import annotations

import copy

from .degradation_model import ContinuousDegradationModel
from .engine_model import ReducedOrderPistonEngine

FAULTS = {"none", "overheating", "lubrication", "misfire", "injector", "sensor_drift", "electrical"}

_ENGINE = ReducedOrderPistonEngine()
_DEGRADATION = ContinuousDegradationModel()


def inject_fault(telemetry: dict, fault: str = "none", severity: float = 0.6):
    """Inject a controlled simulated fault and preserve its provenance."""
    data = copy.deepcopy(telemetry)
    fault = str(fault).lower()
    if fault not in FAULTS:
        raise ValueError(f"Unsupported fault '{fault}'. Allowed: {sorted(FAULTS)}")

    strength = max(0.0, min(1.0, float(severity)))

    if fault == "overheating":
        for key in ["EGT1", "EGT2", "EGT3"]:
            data[key] *= 1 + 0.30 * strength
        data["EFI_Water_Temp"] *= 1 + 0.24 * strength
        data["Oil_Temp"] *= 1 + 0.18 * strength
        data["CHT"] *= 1 + 0.26 * strength
    elif fault == "lubrication":
        data["Oil_Pressure"] *= max(0.25, 1 - 0.65 * strength)
        data["Oil_Temp"] *= 1 + 0.28 * strength
    elif fault == "misfire":
        data["Engine_RPM"] *= 1 - 0.09 * strength
        data["EGT1"] *= 1 - 0.25 * strength
        data["EGT2"] *= 1 + 0.03 * strength
    elif fault == "injector":
        data["Fuel_Flow"] *= 1 - 0.32 * strength
        data["MAP_Injector"] *= 1 + 0.45 * strength
        data["EGT3"] *= 1 - 0.20 * strength
    elif fault == "sensor_drift":
        data["EFI_Water_Temp"] += 75 * strength
    elif fault == "electrical":
        data["Battery_Voltage"] *= max(0.55, 1 - 0.30 * strength)
        data["Battery_Current"] -= 30 * strength
        data["Alternator_Temp"] *= 1 + 0.24 * strength

    # Preserve fault provenance for the advisory/dashboard layer. These
    # metadata fields are ignored by the ML feature frames.
    data["Injected_Fault"] = fault
    data["Injected_Fault_Severity"] = strength

    degradation = {
        "injector": 0.0,
        "lubrication": 0.0,
        "thermal": 0.0,
        "mechanical": 0.0,
        "electrical": 0.0,
        "sensor": 0.0,
    }
    mapping = {
        "overheating": "thermal",
        "lubrication": "lubrication",
        "misfire": "mechanical",
        "injector": "injector",
        "sensor_drift": "sensor",
        "electrical": "electrical",
    }
    if fault in mapping:
        degradation[mapping[fault]] = strength
    data["Degradation_State"] = degradation
    data["Degradation_Severity"] = strength

    return data


def mission_adjust(
    telemetry: dict,
    altitude_ft: float = 3000,
    ambient_c: float = 25,
    duration_h: float = 4,
    rapid_throttle: bool = False,
    degradation_rates: dict[str, float] | None = None,
):
    """Generate mission-conditioned telemetry and apply time-dependent degradation."""
    data = copy.deepcopy(telemetry)
    rpm = float(data.get("Engine_RPM", 3000.0))
    fuel_flow = float(data.get("Fuel_Flow", 30.0))
    throttle = max(0.20, min(0.90, fuel_flow / 50.0))
    if rapid_throttle:
        throttle = min(1.0, throttle + 0.08)

    model = _ENGINE.simulate(
        rpm=rpm,
        throttle=throttle,
        altitude_ft=altitude_ft,
        ambient_c=ambient_c,
        load=None,
    )

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

    state = _DEGRADATION.state_at(duration_h, degradation_rates)
    return _DEGRADATION.apply(data, state)

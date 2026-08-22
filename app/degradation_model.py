from __future__ import annotations

from dataclasses import dataclass


COMPONENTS = ("injector", "lubrication", "thermal", "mechanical", "electrical", "sensor")


@dataclass(frozen=True)
class DegradationState:
    injector: float = 0.0
    lubrication: float = 0.0
    thermal: float = 0.0
    mechanical: float = 0.0
    electrical: float = 0.0
    sensor: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in COMPONENTS}

    @staticmethod
    def _clip(value: float) -> float:
        return max(0.0, min(1.0, float(value)))


class ContinuousDegradationModel:
    """Deterministic component degradation model for mission-time simulation.

    Severity is represented on [0, 1]. The model modifies correlated engine
    telemetry instead of creating isolated single-sensor faults.
    """

    def state_at(self, mission_hours: float, rates: dict[str, float] | None = None) -> DegradationState:
        hours = max(0.0, float(mission_hours))
        rates = rates or {}
        values = {name: DegradationState._clip(hours * float(rates.get(name, 0.0))) for name in COMPONENTS}
        return DegradationState(**values)

    def apply(self, telemetry: dict, state: DegradationState) -> dict:
        data = dict(telemetry)
        d = state.as_dict()

        # Injector: fuel-delivery loss changes fuel flow, mixture/EGT and efficiency.
        if d["injector"]:
            x = d["injector"]
            data["Fuel_Flow"] = float(data.get("Fuel_Flow", 0.0)) * (1.0 - 0.18 * x)
            data["EGT1"] = float(data.get("EGT1", 0.0)) * (1.0 - 0.10 * x)
            data["EGT2"] = float(data.get("EGT2", 0.0)) * (1.0 + 0.04 * x)
            data["EGT3"] = float(data.get("EGT3", 0.0)) * (1.0 - 0.08 * x)
            data["Efficiency"] = float(data.get("Efficiency", 0.0)) * (1.0 - 0.16 * x)

        # Lubrication: lower pressure, higher oil temperature and mechanical stress.
        if d["lubrication"]:
            x = d["lubrication"]
            data["Oil_Pressure"] = float(data.get("Oil_Pressure", 0.0)) * (1.0 - 0.45 * x)
            data["Oil_Temp"] = float(data.get("Oil_Temp", 0.0)) * (1.0 + 0.18 * x)
            data["Vibration"] = float(data.get("Vibration", 0.0)) * (1.0 + 0.35 * x)

        # Thermal degradation increases thermal outputs and reduces efficiency.
        if d["thermal"]:
            x = d["thermal"]
            for key in ("EGT1", "EGT2", "EGT3"):
                data[key] = float(data.get(key, 0.0)) * (1.0 + 0.16 * x)
            data["CHT"] = float(data.get("CHT", 0.0)) * (1.0 + 0.20 * x)
            data["Oil_Temp"] = float(data.get("Oil_Temp", 0.0)) * (1.0 + 0.12 * x)
            data["Efficiency"] = float(data.get("Efficiency", 0.0)) * (1.0 - 0.10 * x)

        # Mechanical degradation primarily appears as vibration and small RPM loss.
        if d["mechanical"]:
            x = d["mechanical"]
            data["Vibration"] = float(data.get("Vibration", 0.0)) * (1.0 + 0.80 * x)
            data["Engine_RPM"] = float(data.get("Engine_RPM", 0.0)) * (1.0 - 0.04 * x)
            data["Oil_Pressure"] = float(data.get("Oil_Pressure", 0.0)) * (1.0 - 0.08 * x)

        # Electrical degradation affects voltage/current/alternator temperature.
        if d["electrical"]:
            x = d["electrical"]
            data["Battery_Voltage"] = float(data.get("Battery_Voltage", 0.0)) * (1.0 - 0.12 * x)
            data["Battery_Current"] = float(data.get("Battery_Current", 0.0)) * (1.0 - 0.18 * x)
            data["Alternator_Temp"] = float(data.get("Alternator_Temp", 0.0)) * (1.0 + 0.20 * x)

        # Sensor degradation is represented as measurement bias; it does not alter engine physics.
        if d["sensor"]:
            x = d["sensor"]
            data["EFI_Water_Temp"] = float(data.get("EFI_Water_Temp", 0.0)) + 20.0 * x
            data["MAP_Injector"] = float(data.get("MAP_Injector", 0.0)) * (1.0 + 0.08 * x)

        data["Degradation_Severity"] = max(d.values())
        data["Degradation_State"] = d
        return data

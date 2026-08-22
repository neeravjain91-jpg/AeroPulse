"""Reduced-order aero-piston engine behavior model for AeroPulse.

This module is deliberately a software demonstrator, not a certified engine
thermodynamic model. It produces bounded, internally consistent telemetry from
mission/operating inputs so the Digital Twin can reason over expected behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class EngineInputs:
    rpm: float = 3000.0
    throttle: float = 0.60
    altitude_ft: float = 3000.0
    ambient_c: float = 25.0
    load: float | None = None


class ReducedOrderPistonEngine:
    """Simple coupled operating/thermal/lubrication/mechanical model."""

    def __init__(self, reference_rpm: float = 3000.0):
        self.reference_rpm = reference_rpm

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    @staticmethod
    def air_density_ratio(altitude_ft: float, ambient_c: float) -> float:
        altitude_km = max(0.0, altitude_ft) / 3280.84
        temp_ratio = (ambient_c + 273.15) / 288.15
        density = math.exp(-altitude_km / 8.4) / temp_ratio
        return max(0.55, min(1.15, density))

    def predict(self, inputs: EngineInputs) -> dict[str, float]:
        throttle = self._clamp(float(inputs.throttle), 0.0, 1.0)
        rpm = self._clamp(float(inputs.rpm), 1200.0, 4000.0)
        ambient_c = self._clamp(float(inputs.ambient_c), -40.0, 60.0)
        altitude_ft = self._clamp(float(inputs.altitude_ft), 0.0, 40000.0)
        density_ratio = self.air_density_ratio(altitude_ft, ambient_c)

        rpm_ratio = rpm / self.reference_rpm
        aerodynamic_load = self._clamp(throttle * (0.65 + 0.35 * rpm_ratio), 0.05, 1.15)
        load = self._clamp(
            aerodynamic_load if inputs.load is None else float(inputs.load), 0.05, 1.15
        )

        fuel_flow = 18.0 + 105.0 * load * (0.82 + 0.18 * rpm_ratio) / math.sqrt(density_ratio)
        combustion_factor = self._clamp(0.82 + 0.18 * density_ratio, 0.65, 1.05)
        base_egt = 410.0 + 315.0 * load * combustion_factor + 22.0 * (rpm_ratio - 1.0)
        thermal_factor = 1.0 + max(0.0, ambient_c - 25.0) * 0.004
        egt_mean = base_egt * thermal_factor

        cht = 82.0 + 88.0 * load * thermal_factor + 10.0 * (1.0 - density_ratio)
        oil_temp = 70.0 + 55.0 * load * thermal_factor
        oil_pressure = self._clamp(72.0 + 12.0 * rpm_ratio - 18.0 * load, 35.0, 95.0)
        vibration = 0.10 + 0.20 * rpm_ratio**2 + 0.35 * load**2
        efficiency = self._clamp(0.30 + 0.43 * load * combustion_factor - 0.08 * abs(rpm_ratio - 1.0), 0.20, 0.78)

        egt1 = egt_mean * 0.985
        egt2 = egt_mean * 1.012
        egt3 = egt_mean

        map_injector = 65.0 + 35.0 * throttle * density_ratio
        battery_voltage = self._clamp(13.7 - 0.35 * load, 12.4, 14.2)
        battery_current = 4.0 + 18.0 * load
        alternator_temp = 45.0 + 35.0 * load + max(0.0, ambient_c - 25.0) * 0.25
        efi_fuel_temp = ambient_c + 18.0 + 0.10 * oil_temp
        efi_water_temp = ambient_c + 42.0 + 0.35 * (cht - 80.0)

        return {
            "Engine_RPM": rpm,
            "EGT1": egt1,
            "EGT2": egt2,
            "EGT3": egt3,
            "CHT": cht,
            "Fuel_Flow": fuel_flow,
            "Oil_Temp": oil_temp,
            "Oil_Pressure": oil_pressure,
            "Battery_Voltage": battery_voltage,
            "Battery_Current": battery_current,
            "Alternator_Temp": alternator_temp,
            "EFI_Fuel_Temp": efi_fuel_temp,
            "EFI_Water_Temp": efi_water_temp,
            "MAP_Injector": map_injector,
            "Vibration": vibration,
            "Efficiency": efficiency,
            "Load": load,
            "Air_Density_Ratio": density_ratio,
        }

    def simulate(
        self,
        rpm: float = 3000.0,
        throttle: float = 0.60,
        altitude_ft: float = 3000.0,
        ambient_c: float = 25.0,
        load: float | None = None,
    ) -> dict[str, float]:
        """Convenience runtime interface used by the mission simulator."""
        return self.predict(
            EngineInputs(
                rpm=rpm,
                throttle=throttle,
                altitude_ft=altitude_ft,
                ambient_c=ambient_c,
                load=load,
            )
        )

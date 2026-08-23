"""Thermodynamic and Reduced-Order Physics Model for MALE UAV Aero Piston Engines."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class EngineInputs:
    """Input operating conditions for the aero-piston engine."""
    rpm: float = 3000.0
    throttle: float = 0.60
    altitude_ft: float = 3000.0
    ambient_c: float = 25.0
    load: Optional[float] = None
    rapid_throttle: bool = False


@dataclass
class EngineState:
    """Estimated internal thermodynamic state of the engine."""
    air_density_ratio: float
    ambient_pressure_kpa: float
    ambient_temp_k: float
    manifold_pressure_kpa: float
    volumetric_efficiency: float
    indicated_power_kw: float
    brake_power_kw: float
    thermal_efficiency: float
    peak_cylinder_pressure_bar: float
    bsfc_g_kwh: float


class ReducedOrderPistonEngine:
    """
    Reduced-order physics and thermodynamic model calibrated for MALE UAV
    piston propulsion systems.
    """

    DISPLACEMENT_L: float = 1.352
    COMPRESSION_RATIO: float = 9.0
    NUM_CYLINDERS: int = 4
    NOMINAL_RPM: float = 3000.0
    MAX_RPM: float = 5800.0
    IDLE_RPM: float = 1400.0
    BASE_POWER_KW: float = 84.5
    TURBO_CRITICAL_ALT_FT: float = 15000.0

    def __init__(self):
        self.gamma: float = 1.33
        self.fuel_lhv_mj_kg: float = 43.5

    @staticmethod
    def _isa_atmosphere(altitude_ft: float, sea_level_temp_c: float = 15.0) -> tuple[float, float, float]:
        """
        Computes International Standard Atmosphere (ISA) properties.
        Returns: (ambient_temp_k, ambient_pressure_kpa, air_density_ratio_sigma)
        """
        h_m = max(0.0, float(altitude_ft) * 0.3048)
        t0_k = 273.15 + float(sea_level_temp_c)
        p0_kpa = 101.325
        rho0 = 1.225

        lapse_rate = 0.0065
        g = 9.80665
        r_air = 287.058

        if h_m <= 11000.0:
            t_amb_k = t0_k - lapse_rate * h_m
            p_amb_kpa = p0_kpa * math.pow(max(t_amb_k / t0_k, 0.05), g / (lapse_rate * r_air))
        else:
            t_trop_k = t0_k - lapse_rate * 11000.0
            p_trop_kpa = p0_kpa * math.pow(t_trop_k / t0_k, g / (lapse_rate * r_air))
            t_amb_k = t_trop_k
            p_amb_kpa = p_trop_kpa * math.exp(-g * (h_m - 11000.0) / (r_air * t_trop_k))

        rho_amb = (p_amb_kpa * 1000.0) / (r_air * max(t_amb_k, 100.0))
        sigma = rho_amb / rho0
        sigma = max(0.55, min(1.15, sigma))

        return t_amb_k, p_amb_kpa, sigma

    def estimate_state(self, inputs: EngineInputs) -> EngineState:
        """Estimates internal thermodynamic cycle parameters."""
        rpm = max(self.IDLE_RPM, min(self.MAX_RPM, float(inputs.rpm)))
        throttle = float(inputs.load) if inputs.load is not None else float(inputs.throttle)
        throttle = max(0.05, min(1.0, throttle))
        altitude_ft = max(0.0, float(inputs.altitude_ft))
        ambient_c = float(inputs.ambient_c)

        t_amb_k, p_amb_kpa, sigma = self._isa_atmosphere(altitude_ft, ambient_c)

        # Manifold pressure scales with throttle and drops with ambient density
        map_kpa = 101.325 * (0.35 + 0.65 * throttle) * (0.60 + 0.40 * sigma)
        map_kpa = max(28.0, map_kpa)

        rpm_ratio = rpm / self.NOMINAL_RPM
        vol_eff = (0.84 + 0.12 * throttle - 0.05 * math.pow(rpm_ratio - 1.0, 2)) * math.sqrt(sigma)
        vol_eff = max(0.45, min(1.05, vol_eff))

        air_mass_flow_index = (map_kpa / 101.325) * vol_eff * (rpm / self.NOMINAL_RPM)
        indicated_power_kw = self.BASE_POWER_KW * air_mass_flow_index * 1.12

        friction_loss_kw = 6.5 + 8.5 * math.pow(rpm / self.MAX_RPM, 1.8)
        brake_power_kw = max(3.0, indicated_power_kw - friction_loss_kw)

        thermal_eff = 0.32 * (1.0 - math.pow(1.0 / self.COMPRESSION_RATIO, self.gamma - 1.0) / 0.58)
        thermal_eff = max(0.24, min(0.38, thermal_eff * (0.85 + 0.15 * throttle)))

        p_max_bar = (map_kpa / 100.0) * math.pow(self.COMPRESSION_RATIO, self.gamma) * (1.2 + 0.6 * throttle)
        bsfc_g_kwh = (3600.0 / (self.fuel_lhv_mj_kg * thermal_eff)) * (1.0 + 0.15 * math.pow(1.0 - throttle, 2))

        return EngineState(
            air_density_ratio=round(sigma, 4),
            ambient_pressure_kpa=round(p_amb_kpa, 2),
            ambient_temp_k=round(t_amb_k, 2),
            manifold_pressure_kpa=round(map_kpa, 2),
            volumetric_efficiency=round(vol_eff, 4),
            indicated_power_kw=round(indicated_power_kw, 2),
            brake_power_kw=round(brake_power_kw, 2),
            thermal_efficiency=round(thermal_eff, 4),
            peak_cylinder_pressure_bar=round(p_max_bar, 2),
            bsfc_g_kwh=round(bsfc_g_kwh, 1),
        )

    def predict(self, inputs: EngineInputs) -> dict[str, float]:
        """Calculates telemetry values matching ACES / UAV sensor channels."""
        rpm = max(self.IDLE_RPM, min(self.MAX_RPM, float(inputs.rpm)))
        throttle = float(inputs.load) if inputs.load is not None else float(inputs.throttle)
        throttle = max(0.05, min(1.0, throttle))
        altitude_ft = max(0.0, float(inputs.altitude_ft))
        ambient_c = float(inputs.ambient_c)
        load = float(inputs.load) if inputs.load is not None else throttle * 0.95

        state = self.estimate_state(inputs)
        thermal_load = state.indicated_power_kw / self.BASE_POWER_KW

        base_egt = 1180.0 + 220.0 * throttle + 40.0 * (altitude_ft / 10000.0) + 1.2 * ambient_c
        egt1 = base_egt + 12.0 * math.sin(rpm * 0.01)
        egt2 = base_egt - 8.0 + 10.0 * math.cos(rpm * 0.01)
        egt3 = base_egt + 4.0 - 6.0 * math.sin(rpm * 0.015)

        cht = 195.0 + 110.0 * thermal_load + 0.9 * ambient_c + 8.0 * (altitude_ft / 10000.0)
        water_temp_c = 78.0 + 14.0 * thermal_load + 0.35 * (ambient_c - 25.0) + 2.5 * (altitude_ft / 10000.0)
        oil_temp_c = 82.0 + 18.0 * thermal_load + 0.38 * (ambient_c - 25.0) + 3.0 * (altitude_ft / 10000.0)

        viscosity_factor = max(0.65, 1.0 - 0.005 * (oil_temp_c - 85.0))
        oil_press_psi = (32.0 + 38.0 * (rpm / self.NOMINAL_RPM)) * viscosity_factor

        # Fuel Flow scales with throttle, load, and increases with altitude for power enrichment
        base_ff = (12.0 + 18.0 * throttle) * (0.85 + 0.30 * (rpm / self.NOMINAL_RPM))
        fuel_flow_l_h = base_ff * (1.0 + 0.25 * (altitude_ft / 25000.0))
        map_injector = (state.manifold_pressure_kpa / 101.325) * 29.92
        fuel_temp_c = max(ambient_c + 5.0, 24.0 + 0.25 * water_temp_c + 0.2 * ambient_c)

        battery_voltage = 28.2 - 0.4 * (load - 0.5) - 0.02 * (ambient_c - 25.0)
        battery_current = 14.0 + 18.0 * load + 4.0 * math.sin(rpm * 0.02)
        alternator_temp_c = 48.0 + 26.0 * (battery_current / 35.0) + 0.6 * ambient_c

        vibration_g = 0.85 + 0.75 * math.pow(rpm / self.NOMINAL_RPM, 2.0) + 0.45 * (load - 0.5)

        return {
            "Engine_RPM": round(rpm, 1),
            "EGT1": round(egt1, 1),
            "EGT2": round(egt2, 1),
            "EGT3": round(egt3, 1),
            "CHT": round(cht, 1),
            "Fuel_Flow": round(fuel_flow_l_h, 2),
            "Oil_Temp": round(oil_temp_c, 1),
            "Oil_Pressure": round(oil_press_psi, 1),
            "Battery_Voltage": round(battery_voltage, 2),
            "Battery_Current": round(battery_current, 2),
            "Alternator_Temp": round(alternator_temp_c, 1),
            "EFI_Fuel_Temp": round(fuel_temp_c, 1),
            "EFI_Water_Temp": round(water_temp_c, 1),
            "MAP_Injector": round(map_injector, 2),
            "Vibration": round(vibration_g, 3),
            "Efficiency": round(state.thermal_efficiency, 4),
            "Load": round(load, 3),
            "Air_Density_Ratio": round(state.air_density_ratio, 4),
            "Indicated_Power_kW": round(state.indicated_power_kw, 2),
            "Brake_Power_kW": round(state.brake_power_kw, 2),
            "Peak_Pressure_bar": round(state.peak_cylinder_pressure_bar, 2),
        }

    def simulate(
        self,
        rpm: float = 3000.0,
        throttle: float = 0.60,
        altitude_ft: float = 3000.0,
        ambient_c: float = 25.0,
        load: Optional[float] = None,
        rapid_throttle: bool = False,
    ) -> dict[str, float]:
        inputs = EngineInputs(
            rpm=rpm,
            throttle=throttle,
            altitude_ft=altitude_ft,
            ambient_c=ambient_c,
            load=load,
            rapid_throttle=rapid_throttle,
        )
        return self.predict(inputs)

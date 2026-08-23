"""Thermodynamic and Reduced-Order Physics Model for MALE UAV Aero Piston Engines.

This module provides a first-principles grounded physics engine simulator and
virtual sensor state-estimator representing a turbocharged 4-stroke aero-piston
engine (such as the Rotax 914/915 iS or Austro Engine AE300 heavy-fuel platform)
operating in MALE UAV mission envelopes (0 to 30,000 ft, -40°C to +50°C ambient).

Core capabilities:
1. International Standard Atmosphere (ISA) barometric and thermal lapse modeling.
2. Turbocharger compressor map, wastegate regulation, and intercooling.
3. In-cylinder Otto/Diesel thermodynamic cycle, indicated work, and volumetric efficiency.
4. Multi-subsystem heat rejection networks (CHT, EGT1-3, Coolant, Oil).
5. Lubrication circuit hydrodynamics (oil pressure vs RPM, temperature, viscosity).
6. Electrical generation and alternator thermal balance.
7. Virtual sensor state estimation (Pmax, Indicated Power, BSFC, Thermal Efficiency).
"""
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

    # Engine baseline physical characteristics (4-cylinder, 1.35L displacement, turbocharged)
    DISPLACEMENT_L: float = 1.352
    COMPRESSION_RATIO: float = 9.0
    NUM_CYLINDERS: int = 4
    NOMINAL_RPM: float = 3000.0
    MAX_RPM: float = 5800.0
    IDLE_RPM: float = 1400.0
    BASE_POWER_KW: float = 84.5  # ~115 hp class
    TURBO_CRITICAL_ALT_FT: float = 15000.0  # Turbo maintains sea-level MAP up to critical altitude

    def __init__(self):
        # Specific heat ratio for air-fuel mixture
        self.gamma: float = 1.33
        # Fuel Lower Heating Value (LHV) in MJ/kg (AvGas 100LL / Jet-A1 approx 43.5 MJ/kg)
        self.fuel_lhv_mj_kg: float = 43.5

    @staticmethod
    def _isa_atmosphere(altitude_ft: float, sea_level_temp_c: float = 15.0) -> tuple[float, float, float]:
        """
        Computes International Standard Atmosphere (ISA) properties.
        
        Returns:
            (ambient_temp_k, ambient_pressure_kpa, air_density_ratio_sigma)
        """
        h_m = max(0.0, float(altitude_ft) * 0.3048)  # Altitude in meters
        t0_k = 273.15 + float(sea_level_temp_c)
        p0_kpa = 101.325
        rho0 = 1.225  # kg/m3

        # Troposphere temperature lapse rate: -0.0065 K/m up to 11,000m
        lapse_rate = 0.0065
        g = 9.80665
        r_air = 287.058  # J/(kg*K)

        if h_m <= 11000.0:
            t_amb_k = t0_k - lapse_rate * h_m
            p_amb_kpa = p0_kpa * math.pow(max(t_amb_k / t0_k, 0.05), g / (lapse_rate * r_air))
        else:
            # Tropopause isothermal layer (11km to 20km)
            t_trop_k = t0_k - lapse_rate * 11000.0
            p_trop_kpa = p0_kpa * math.pow(t_trop_k / t0_k, g / (lapse_rate * r_air))
            t_amb_k = t_trop_k
            p_amb_kpa = p_trop_kpa * math.exp(-g * (h_m - 11000.0) / (r_air * t_trop_k))

        rho_amb = (p_amb_kpa * 1000.0) / (r_air * max(t_amb_k, 100.0))
        sigma = rho_amb / rho0

        return t_amb_k, p_amb_kpa, sigma

    def estimate_state(self, inputs: EngineInputs) -> EngineState:
        """Estimates internal thermodynamic cycle parameters."""
        rpm = max(self.IDLE_RPM, min(self.MAX_RPM, float(inputs.rpm)))
        throttle = max(0.05, min(1.0, float(inputs.throttle)))
        altitude_ft = max(0.0, float(inputs.altitude_ft))
        ambient_c = float(inputs.ambient_c)

        t_amb_k, p_amb_kpa, sigma = self._isa_atmosphere(altitude_ft, ambient_c)

        # Turbocharger boost regulation
        # Turbo maintains high MAP up to critical altitude; beyond that MAP decays with ambient pressure
        if altitude_ft <= self.TURBO_CRITICAL_ALT_FT:
            turbo_boost_kpa = 38.0 * throttle  # Up to ~139 kPa absolute MAP at full throttle
            map_kpa = min(101.325 + turbo_boost_kpa, 101.325 * (0.35 + 0.95 * throttle))
        else:
            altitude_decay = math.exp(-(altitude_ft - self.TURBO_CRITICAL_ALT_FT) / 25000.0)
            map_kpa = (p_amb_kpa + 38.0 * throttle) * altitude_decay

        map_kpa = max(28.0, map_kpa)  # Minimum intake manifold pressure

        # Volumetric efficiency based on RPM and throttle
        rpm_ratio = rpm / self.NOMINAL_RPM
        vol_eff = (0.84 + 0.12 * throttle - 0.05 * math.pow(rpm_ratio - 1.0, 2)) * math.sqrt(sigma)
        vol_eff = max(0.45, min(1.05, vol_eff))

        # Indicated Power (P_ind = (Vd * n * RPM * IMEP) / 120)
        # Power scales with air mass flow: m_dot_air ~ MAP * Vol_eff * RPM
        air_mass_flow_index = (map_kpa / 101.325) * vol_eff * (rpm / self.NOMINAL_RPM)
        indicated_power_kw = self.BASE_POWER_KW * air_mass_flow_index * 1.12

        # Friction and pumping losses (FMEP ~ a + b*RPM)
        friction_loss_kw = 6.5 + 8.5 * math.pow(rpm / self.MAX_RPM, 1.8)
        brake_power_kw = max(3.0, indicated_power_kw - friction_loss_kw)

        # Thermal efficiency (Otto/Diesel cycle approximation)
        thermal_eff = 0.32 * (1.0 - math.pow(1.0 / self.COMPRESSION_RATIO, self.gamma - 1.0) / 0.58)
        thermal_eff = max(0.24, min(0.38, thermal_eff * (0.85 + 0.15 * throttle)))

        # In-cylinder peak pressure (bar)
        p_max_bar = (map_kpa / 100.0) * math.pow(self.COMPRESSION_RATIO, self.gamma) * (1.2 + 0.6 * throttle)

        # Brake Specific Fuel Consumption (BSFC) in g/kWh
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
        """
        Calculates telemetry values matching ACES / UAV sensor channels.
        """
        rpm = max(self.IDLE_RPM, min(self.MAX_RPM, float(inputs.rpm)))
        throttle = max(0.05, min(1.0, float(inputs.throttle)))
        altitude_ft = max(0.0, float(inputs.altitude_ft))
        ambient_c = float(inputs.ambient_c)
        load = float(inputs.load) if inputs.load is not None else throttle * 0.95

        state = self.estimate_state(inputs)

        # -------------------------------------------------------------
        # 1. Thermal Balance Network
        # -------------------------------------------------------------
        thermal_load = state.indicated_power_kw / self.BASE_POWER_KW

        # Exhaust Gas Temperature (EGT) in °F (Typical aero piston: 1100°F - 1450°F / 600-800°C)
        base_egt = 1180.0 + 220.0 * throttle + 40.0 * (altitude_ft / 10000.0) + 1.2 * ambient_c
        egt1 = base_egt + 12.0 * math.sin(rpm * 0.01)
        egt2 = base_egt - 8.0 + 10.0 * math.cos(rpm * 0.01)
        egt3 = base_egt + 4.0 - 6.0 * math.sin(rpm * 0.015)

        # Cylinder Head Temperature (CHT) in °F (Typical: 220°F - 360°F / 105-180°C)
        cht = 195.0 + 110.0 * thermal_load + 0.9 * ambient_c + 8.0 * (altitude_ft / 10000.0)

        # Liquid Coolant Temperature (EFI_Water_Temp) in °C (Thermostat controlled 75°C - 95°C)
        water_temp_c = 78.0 + 14.0 * thermal_load + 0.35 * (ambient_c - 25.0) + 2.5 * (altitude_ft / 10000.0)

        # Oil Temperature in °C (Typical: 80°C - 115°C)
        oil_temp_c = 82.0 + 18.0 * thermal_load + 0.38 * (ambient_c - 25.0) + 3.0 * (altitude_ft / 10000.0)

        # -------------------------------------------------------------
        # 2. Lubrication Circuit
        # -------------------------------------------------------------
        # Oil Pressure in PSI (Typical: 40 - 75 PSI)
        viscosity_factor = max(0.65, 1.0 - 0.005 * (oil_temp_c - 85.0))
        oil_press_psi = (32.0 + 38.0 * (rpm / self.NOMINAL_RPM)) * viscosity_factor

        # -------------------------------------------------------------
        # 3. Fuel & Injection Dynamics
        # -------------------------------------------------------------
        # Fuel Flow in L/h or kg/h (Typical: 12 - 38 L/h)
        fuel_flow_kg_h = (state.brake_power_kw * state.bsfc_g_kwh) / 1000.0
        fuel_flow_l_h = fuel_flow_kg_h / 0.72  # Gasoline density ~0.72 kg/L
        # MAP Injector sensor in inHg or kPa representation (e.g. 20 - 45 units)
        map_injector = (state.manifold_pressure_kpa / 101.325) * 29.92

        # Fuel Temperature in °C (Fuel rail heated by engine bay)
        fuel_temp_c = max(ambient_c + 5.0, 24.0 + 0.25 * water_temp_c + 0.2 * ambient_c)

        # -------------------------------------------------------------
        # 4. Electrical Generation & Alternator
        # -------------------------------------------------------------
        # FADEC 28V dual-bus system (Alternator regulated 27.8V - 28.5V)
        battery_voltage = 28.2 - 0.4 * (load - 0.5) - 0.02 * (ambient_c - 25.0)
        battery_current = 14.0 + 18.0 * load + 4.0 * math.sin(rpm * 0.02)
        alternator_temp_c = 48.0 + 26.0 * (battery_current / 35.0) + 0.6 * ambient_c

        # -------------------------------------------------------------
        # 5. Vibration & Dynamic Indicators
        # -------------------------------------------------------------
        vibration_g = 0.85 + 0.75 * math.pow(rpm / self.NOMINAL_RPM, 2.0) + 0.3 * (load - 0.5)

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
            "Efficiency": round(state.thermal_efficiency * 100.0, 2),
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
        """Convenience simulation helper for mission telemetry generators."""
        inputs = EngineInputs(
            rpm=rpm,
            throttle=throttle,
            altitude_ft=altitude_ft,
            ambient_c=ambient_c,
            load=load,
            rapid_throttle=rapid_throttle,
        )
        return self.predict(inputs)

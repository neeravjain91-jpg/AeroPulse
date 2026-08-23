"""Defence-Grade Autonomous Maintenance Advisory System for MALE UAV Propulsion.

Provides operational flight dispatch decisions (GO / CAUTION / NO-GO) and
multi-echelon maintenance action orders (O-Level, I-Level, D-Level) based on
synchronized Digital Twin telemetry and predictive diagnostics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class MaintenanceAction:
    echelon: str  # "O-Level" (Flight-Line), "I-Level" (Field Workshop), "D-Level" (Depot Overhaul)
    dispatch_status: str  # "GO_MISSION_READY", "CAUTION_RESTRICTED_ENVELOPE", "NO_GO_MAINTENANCE_HOLD"
    recommended_action: str
    technical_order: str
    urgency: str
    subsystem: str


def fault_advisory(telemetry: dict, twin: dict, sensor_health: dict | None = None) -> list[tuple[str, str, list[str]]]:
    """
    Evaluates Digital Twin residuals, cross-channel statistics, and sensor integrity
    to isolate failure modes and candidate root causes.
    """
    z = twin["z_scores"]
    findings = []

    # 1. Sensor Instrumentation Fault (Priority isolation)
    if sensor_health and sensor_health.get("suspected_sensor_fault"):
        suspects = sensor_health.get("suspect_channels", [])
        findings.append(
            (
                "Sensor Drift / Instrumentation Bias",
                "medium",
                ["cross-channel discrepancy detected", f"suspect channels: {', '.join(suspects)}"],
            )
        )

    # 2. Lubrication Subsystem Degradation
    if z.get("Oil_Pressure", 0.0) < -1.5 and z.get("Oil_Temp", 0.0) > 1.0:
        findings.append(
            (
                "Lubrication System Degradation / Oil Starvation",
                "high",
                ["low oil pressure residual (<-1.5 sigma)", "elevated oil temperature residual (>+1.0 sigma)"],
            )
        )

    # 3. Severe Overheating & Thermal Runaway
    egt_max_z = max(z.get("EGT1", 0.0), z.get("EGT2", 0.0), z.get("EGT3", 0.0))
    water_z = z.get("EFI_Water_Temp", 0.0)
    cht_z = z.get("CHT", 0.0)

    if max(egt_max_z, water_z, cht_z) > 3.0:
        findings.append(
            (
                "Thermal Runaway / Cooling System Breakdown",
                "high",
                ["temperatures exceeding 3-sigma healthy reference", f"Max CHT z: {cht_z:.2f}, EGT z: {egt_max_z:.2f}"],
            )
        )
    elif max(egt_max_z, water_z, cht_z) > 1.8:
        findings.append(
            (
                "Elevated Thermal Stress / Cooling Degradation",
                "medium",
                ["moderate temperature elevation above healthy reference"],
            )
        )

    # 4. Combustion Instability & Cylinder Misfire
    egt1 = float(telemetry.get("EGT1", 1200.0))
    egt2 = float(telemetry.get("EGT2", 1200.0))
    egt3 = float(telemetry.get("EGT3", 1200.0))
    egt_spread = max(egt1, egt2, egt3) - min(egt1, egt2, egt3)

    if egt_spread > 120.0:
        findings.append(
            (
                "Combustion Imbalance / Single-Cylinder Misfire",
                "high" if egt_spread > 220.0 else "medium",
                [f"EGT delta across cylinders: {egt_spread:.1f}F", "asymmetric exhaust gas thermal release"],
            )
        )

    # 5. Fuel Injection & MAP Abnormality
    if abs(z.get("MAP_Injector", 0.0)) > 2.0 and abs(z.get("Fuel_Flow", 0.0)) > 1.0:
        findings.append(
            (
                "Fuel Injection Rail / Injector Clogging",
                "medium",
                ["manifold injector pressure residual mismatch", "fuel flow delivery anomaly"],
            )
        )

    # 6. Electrical Generation & Alternator Thermal Fault
    if "Battery_Voltage" in z and "Alternator_Temp" in z:
        if z["Battery_Voltage"] < -2.0 and (abs(z.get("Battery_Current", 0.0)) > 1.5 or z["Alternator_Temp"] > 1.5):
            findings.append(
                (
                    "Dual-Bus Alternator / FADEC Electrical Degradation",
                    "high",
                    ["sub-nominal bus voltage residual", "alternator thermal runaway or diode rectifier failure"],
                )
            )

    # 7. Dynamic Vibration Anomaly
    if telemetry.get("Vibration", 1.0) > 2.2:
        findings.append(
            (
                "Abnormal Mechanical Vibration / Dynamic Unbalance",
                "high",
                [f"peak vibration signature {telemetry.get('Vibration', 0.0):.2f}g exceeds structural threshold"],
            )
        )

    # 8. Unclassified Digital Twin Anomaly
    if twin.get("max_abs_z", 0.0) > 3.0 and not findings:
        findings.append(
            (
                "Unclassified Aero-Piston Anomaly",
                "medium",
                ["broad multi-parameter deviation from healthy synchronized twin baseline"],
            )
        )

    if not findings:
        findings = [("Nominal Healthy Propulsion Operation", "low", ["all subsystem parameters within 1.5-sigma baseline"])]

    return findings


def maintenance_advice(findings: list[tuple[str, str, list[str]]], sensor_health: dict | None = None) -> str:
    """Generates human-readable primary operational maintenance directive."""
    name, severity, evidence = findings[0]

    if sensor_health and sensor_health.get("suspected_sensor_fault"):
        channels = ", ".join(sensor_health.get("suspect_channels", [])) or "telemetry transducer"
        return f"[INSTRUMENTATION DIRECTIVE] Calibrate/replace sensor channels ({channels}) before attributing engine mechanical fault."

    if severity == "high":
        return f"[NO-GO FLIGHT HOLD] Critical anomaly detected ({name}). Perform immediate I-Level technical inspection: {evidence[0]}."
    if severity == "medium":
        return f"[CAUTION ADVISORY] Subsystem degradation identified ({name}). Inspect affected components prior to next endurance flight."
    return "[DISPATCH CLEARED] Propulsion parameters synchronized with Digital Twin baseline. Cleared for MALE UAV flight operations."


def detailed_maintenance_action(findings: list[tuple[str, str, list[str]]], sensor_health: dict | None = None) -> MaintenanceAction:
    """Generates structured military-grade maintenance work order."""
    name, severity, evidence = findings[0]

    if sensor_health and sensor_health.get("suspected_sensor_fault"):
        channels = ", ".join(sensor_health.get("suspect_channels", [])) or "transducers"
        return MaintenanceAction(
            echelon="O-Level (Flight Line)",
            dispatch_status="CAUTION_RESTRICTED_ENVELOPE",
            recommended_action=f"Hook up Ground Support Equipment (GSE). Validate sensor harnesses and recalibrate {channels}.",
            technical_order="TO-UAV-AVIONICS-4-12",
            urgency="PRE-FLIGHT",
            subsystem="Sensors & Instrumentation",
        )

    if "Lubrication" in name:
        return MaintenanceAction(
            echelon="I-Level (Field Maintenance)",
            dispatch_status="NO_GO_MAINTENANCE_HOLD",
            recommended_action="Check oil scavenge screens, inspect oil filter for metal debris/spalling, test oil pump bypass relief valve.",
            technical_order="TO-UAV-ENG-LUB-02",
            urgency="IMMEDIATE",
            subsystem="Lubrication Circuit",
        )

    if "Thermal" in name or "Cooling" in name:
        return MaintenanceAction(
            echelon="I-Level (Field Maintenance)",
            dispatch_status="NO_GO_MAINTENANCE_HOLD",
            recommended_action="Inspect coolant radiator for FOD/clogging, verify thermostat actuation, check coolant pump impeller integrity.",
            technical_order="TO-UAV-ENG-THM-07",
            urgency="IMMEDIATE",
            subsystem="Cooling System",
        )

    if "Combustion" in name or "Misfire" in name:
        return MaintenanceAction(
            echelon="O-Level (Flight Line)",
            dispatch_status="CAUTION_RESTRICTED_ENVELOPE",
            recommended_action="Perform differential compression check across cylinders 1-4, inspect dual-spark plugs, clean fuel injector nozzles.",
            technical_order="TO-UAV-ENG-IGN-03",
            urgency="PRIOR_TO_NEXT_SORTIE",
            subsystem="Ignition & Combustion",
        )

    if "Fuel" in name:
        return MaintenanceAction(
            echelon="O-Level (Flight Line)",
            dispatch_status="CAUTION_RESTRICTED_ENVELOPE",
            recommended_action="Flow-test electronic fuel injectors, inspect high-pressure fuel pump filter, verify fuel rail pressure sensor.",
            technical_order="TO-UAV-ENG-FUEL-01",
            urgency="PRIOR_TO_NEXT_SORTIE",
            subsystem="Fuel Delivery",
        )

    if "Electrical" in name:
        return MaintenanceAction(
            echelon="O-Level (Flight Line)",
            dispatch_status="NO_GO_MAINTENANCE_HOLD",
            recommended_action="Test internal alternator rectifier diodes, inspect stator windings, verify FADEC dual-bus voltage regulator.",
            technical_order="TO-UAV-ELEC-PWR-05",
            urgency="IMMEDIATE",
            subsystem="Electrical & FADEC",
        )

    if "Vibration" in name:
        return MaintenanceAction(
            echelon="I-Level (Field Maintenance)",
            dispatch_status="NO_GO_MAINTENANCE_HOLD",
            recommended_action="Perform dynamic propeller & crankshaft balancing check. Inspect engine isolation shock mounts for tear.",
            technical_order="TO-UAV-ENG-DYN-09",
            urgency="IMMEDIATE",
            subsystem="Mechanical & Dynamics",
        )

    return MaintenanceAction(
        echelon="O-Level (Flight Line)",
        dispatch_status="GO_MISSION_READY",
        recommended_action="Routine turnaround servicing. Inspect fluid levels and check logbook signatures.",
        technical_order="TO-UAV-ENG-ROUTINE-01",
        urgency="ROUTINE",
        subsystem="General Propulsion",
    )

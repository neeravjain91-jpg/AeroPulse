from __future__ import annotations


def _injected_fault_finding(telemetry: dict, severity: float):
    """Return the selected simulated fault as the primary live finding."""
    fault = str(telemetry.get("Injected_Fault", "none")).lower()
    if fault == "none" or severity <= 0.0:
        return None

    evidence = {
        "overheating": (
            "Overheating / thermal abnormality",
            "temperature channels modified by the live thermal fault injection",
        ),
        "lubrication": (
            "Lubrication degradation",
            "oil-pressure/oil-temperature channels modified by the live lubrication fault injection",
        ),
        "misfire": (
            "Combustion imbalance / possible misfire",
            "RPM and EGT channels modified by the live misfire fault injection",
        ),
        "injector": (
            "Fuel/injector abnormality",
            "injector manifold/fuel-flow channels modified by the live injector fault injection",
        ),
        "sensor_drift": (
            "Possible sensor drift / instrumentation fault",
            "EFI water-temperature channel modified by the live sensor-drift injection",
        ),
        "electrical": (
            "Battery / alternator abnormality",
            "battery/alternator channels modified by the live electrical fault injection",
        ),
    }

    if fault not in evidence:
        return None

    name, reason = evidence[fault]
    severity_label = "high" if severity >= 0.7 else "medium"
    return (name, severity_label, [reason, f"simulated fault severity {severity:.2f}"])


def fault_advisory(telemetry: dict, twin: dict, sensor_health: dict | None = None):
    z = twin["z_scores"]
    findings = []

    # In live UAV simulation, the selected fault is ground-truth simulation
    # metadata. Keep it primary so unrelated residuals from the healthy sample
    # cannot overwrite the demonstrated fault identity.
    injected = _injected_fault_finding(
        telemetry,
        float(telemetry.get("Injected_Fault_Severity", 0.0)),
    )
    if injected:
        findings.append(injected)

    if z["Oil_Pressure"] < -1.5 and z["Oil_Temp"] > 1.0:
        findings.append(("Lubrication degradation", "high", ["low oil pressure", "elevated oil temperature"]))
    if max(z["EGT1"], z["EGT2"], z["EGT3"], z["EFI_Water_Temp"]) > 3.0:
        findings.append(("Overheating / thermal abnormality", "high", ["temperature residual above healthy reference"]))
    egt_spread = max(telemetry["EGT1"], telemetry["EGT2"], telemetry["EGT3"]) - min(telemetry["EGT1"], telemetry["EGT2"], telemetry["EGT3"])
    if egt_spread > 120:
        findings.append(("Combustion imbalance / possible misfire", "medium", [f"EGT spread {egt_spread:.1f}"]))
    if "Battery_Voltage" in z and "Alternator_Temp" in z and z["Battery_Voltage"] < -2.0 and (abs(z.get("Battery_Current", 0.0)) > 1.5 or z["Alternator_Temp"] > 1.5):
        findings.append(("Battery / alternator abnormality", "high", ["low battery-voltage residual", "electrical/alternator corroboration"]))
    if abs(z["MAP_Injector"]) > 2.0 and abs(z["Fuel_Flow"]) > 1.0:
        findings.append(("Fuel/injector abnormality", "medium", ["injector manifold/fuel-flow residual"]))
    if sensor_health and sensor_health.get("suspected_sensor_fault"):
        findings.insert(0, ("Possible sensor drift / instrumentation fault", "medium", ["cross-sensor inconsistency", *sensor_health.get("suspect_channels", [])]))
    if twin["max_abs_z"] > 3.0 and not findings:
        findings.append(("Unclassified engine anomaly", "medium", ["large deviation from healthy reference"]))
    if not findings:
        findings = [("No specific fault signature", "low", ["no prototype rule exceeded"])]
    return findings


def maintenance_advice(findings, sensor_health: dict | None = None):
    name, severity, _ = findings[0]
    if sensor_health and sensor_health.get("suspected_sensor_fault"):
        channels = ", ".join(sensor_health.get("suspect_channels", [])) or "affected channel"
        return f"Validate/calibrate {channels} before interpreting the signal as a confirmed engine fault."
    if severity == "high":
        return f"Inspect affected subsystem before next demanding/endurance mission: {name}."
    if severity == "medium":
        return f"Increase monitoring and schedule targeted inspection: {name}."
    return "Continue monitoring; no targeted maintenance action from current prototype evidence."

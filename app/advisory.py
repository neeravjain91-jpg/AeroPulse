def fault_advisory(telemetry: dict, twin: dict):
    z = twin["z_scores"]
    findings = []

    # Prototype heuristic rules; not certified engine diagnostics.
    if z["Oil_Pressure"] < -1.5 and z["Oil_Temp"] > 1.0:
        findings.append(
            (
                "Lubrication degradation",
                "high",
                ["low oil pressure", "elevated oil temperature"],
            )
        )

    if max(z["EGT1"], z["EGT2"], z["EGT3"], z["EFI_Water_Temp"]) > 2.0:
        findings.append(
            (
                "Overheating / thermal abnormality",
                "high",
                ["temperature residual above healthy reference"],
            )
        )

    egt_spread = max(telemetry["EGT1"], telemetry["EGT2"], telemetry["EGT3"]) - min(
        telemetry["EGT1"], telemetry["EGT2"], telemetry["EGT3"]
    )
    if egt_spread > 120:
        findings.append(
            (
                "Combustion imbalance / possible misfire",
                "medium",
                [f"EGT spread {egt_spread:.1f}"],
            )
        )

    if abs(z["MAP_Injector"]) > 2.0 and abs(z["Fuel_Flow"]) > 1.0:
        findings.append(
            (
                "Fuel/injector abnormality",
                "medium",
                ["injector manifold/fuel-flow residual"],
            )
        )

    if twin["max_abs_z"] > 3.0 and not findings:
        findings.append(
            (
                "Unclassified engine anomaly",
                "medium",
                ["large deviation from healthy reference"],
            )
        )

    if not findings:
        findings = [("No specific fault signature", "low", ["no prototype rule exceeded"])]

    return findings


def maintenance_advice(findings):
    name, severity, _ = findings[0]
    if severity == "high":
        return f"Inspect affected subsystem before next demanding/endurance mission: {name}."
    if severity == "medium":
        return f"Increase monitoring and schedule targeted inspection: {name}."
    return "Continue monitoring; no targeted maintenance action from current prototype evidence."

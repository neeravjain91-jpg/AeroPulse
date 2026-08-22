from app.mission_whatif import MissionScenario
from app.mission_whatif_rul import MissionWhatIfRUL


def _telemetry():
    return {
        "Engine_RPM": 3000.0,
        "EGT1": 650.0,
        "EGT2": 652.0,
        "EGT3": 648.0,
        "CHT": 145.0,
        "Fuel_Flow": 30.0,
        "Oil_Temp": 90.0,
        "Oil_Pressure": 60.0,
        "Battery_Voltage": 24.0,
        "Battery_Current": 20.0,
        "Alternator_Temp": 70.0,
        "EFI_Water_Temp": 80.0,
        "MAP_Injector": 90.0,
        "Vibration": 0.5,
        "Efficiency": 0.65,
    }


RATES = {"injector": 0.05, "lubrication": 0.04, "thermal": 0.03, "mechanical": 0.02, "electrical": 0.01, "sensor": 0.02}


def test_scenario_run_contains_rul():
    engine = MissionWhatIfRUL(RATES)
    result = engine.run(_telemetry(), MissionScenario("baseline", duration_h=4))
    assert "rul" in result
    assert result["rul"]["rul_hours"] >= 0


def test_longer_mission_has_more_degradation_and_lower_rul():
    engine = MissionWhatIfRUL(RATES)
    short = engine.run(_telemetry(), MissionScenario("short", duration_h=2))
    long = engine.run(_telemetry(), MissionScenario("endurance", duration_h=8))
    assert long["degradation_severity"] > short["degradation_severity"]
    assert long["rul"]["rul_hours"] < short["rul"]["rul_hours"]


def test_what_if_comparison_reports_rul_impact():
    engine = MissionWhatIfRUL(RATES)
    comparison = engine.compare(
        _telemetry(),
        MissionScenario("baseline", altitude_ft=10000, ambient_c=25, duration_h=4),
        MissionScenario("hot-high-endurance", altitude_ft=25000, ambient_c=45, duration_h=8),
    )
    assert "rul_hours" in comparison["impact"]
    assert "health_index" in comparison["impact"]
    assert comparison["alternative"]["rul"]["rul_hours"] >= 0

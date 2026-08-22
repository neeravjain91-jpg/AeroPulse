from app.mission_whatif import MissionScenario
from app.mission_whatif_rul import MissionWhatIfRUL


def _telemetry():
    return {
        "Engine_RPM": 3000.0, "EGT1": 650.0, "EGT2": 652.0, "EGT3": 648.0,
        "CHT": 145.0, "Fuel_Flow": 30.0, "Oil_Temp": 90.0,
        "Oil_Pressure": 60.0, "Battery_Voltage": 24.0, "Battery_Current": 20.0,
        "Alternator_Temp": 70.0, "EFI_Water_Temp": 80.0, "MAP_Injector": 90.0,
        "Vibration": 0.5, "Efficiency": 0.65,
    }


RATES = {"injector": 0.05, "lubrication": 0.04, "thermal": 0.03, "mechanical": 0.02, "electrical": 0.01, "sensor": 0.02}


def test_higher_altitude_changes_mission_response():
    engine = MissionWhatIfRUL(RATES)
    low = engine.run(_telemetry(), MissionScenario("low", altitude_ft=5000, ambient_c=25, duration_h=4))
    high = engine.run(_telemetry(), MissionScenario("high", altitude_ft=25000, ambient_c=25, duration_h=4))
    assert high["telemetry"]["Air_Density_Ratio"] < low["telemetry"]["Air_Density_Ratio"]
    assert high["fuel_flow"] != low["fuel_flow"]


def test_hotter_mission_changes_thermal_state():
    engine = MissionWhatIfRUL(RATES)
    normal = engine.run(_telemetry(), MissionScenario("normal", ambient_c=25, duration_h=4))
    hot = engine.run(_telemetry(), MissionScenario("hot", ambient_c=45, duration_h=4))
    assert hot["cht"] > normal["cht"]
    assert hot["telemetry"]["Oil_Temp"] > normal["telemetry"]["Oil_Temp"]


def test_longer_endurance_reduces_rul():
    engine = MissionWhatIfRUL(RATES)
    short = engine.run(_telemetry(), MissionScenario("short", duration_h=2))
    long = engine.run(_telemetry(), MissionScenario("long", duration_h=10))
    assert long["degradation_severity"] > short["degradation_severity"]
    assert long["rul"]["rul_hours"] < short["rul"]["rul_hours"]


def test_rapid_throttle_changes_rul_inputs():
    engine = MissionWhatIfRUL(RATES)
    normal = engine.run(_telemetry(), MissionScenario("normal", rapid_throttle=False))
    rapid = engine.run(_telemetry(), MissionScenario("rapid", rapid_throttle=True))
    assert rapid["fuel_flow"] > normal["fuel_flow"]
    assert rapid["rul"]["degradation_severity"] >= normal["rul"]["degradation_severity"]

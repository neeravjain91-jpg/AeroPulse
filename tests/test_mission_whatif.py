from app.mission_whatif import MissionScenario, MissionWhatIf


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


def test_high_altitude_changes_what_if_outputs():
    engine = MissionWhatIf(RATES)
    base = engine.run(_telemetry(), MissionScenario("baseline", altitude_ft=3000))
    high = engine.run(_telemetry(), MissionScenario("high-altitude", altitude_ft=25000))
    assert high["telemetry"]["Air_Density_Ratio"] < base["telemetry"]["Air_Density_Ratio"]
    assert high["engine_rpm"] != base["engine_rpm"]


def test_hot_weather_increases_thermal_loading():
    engine = MissionWhatIf(RATES)
    normal = engine.run(_telemetry(), MissionScenario("normal", ambient_c=25))
    hot = engine.run(_telemetry(), MissionScenario("hot", ambient_c=45))
    assert hot["cht"] > normal["cht"]
    assert hot["telemetry"]["Oil_Temp"] > normal["telemetry"]["Oil_Temp"]


def test_endurance_mission_increases_degradation():
    engine = MissionWhatIf(RATES)
    short = engine.run(_telemetry(), MissionScenario("short", duration_h=2))
    endurance = engine.run(_telemetry(), MissionScenario("endurance", duration_h=10))
    assert endurance["degradation_severity"] > short["degradation_severity"]
    assert endurance["health_index"] < short["health_index"]


def test_rapid_throttle_changes_engine_response():
    engine = MissionWhatIf(RATES)
    normal = engine.run(_telemetry(), MissionScenario("normal", rapid_throttle=False))
    rapid = engine.run(_telemetry(), MissionScenario("rapid", rapid_throttle=True))
    assert rapid["fuel_flow"] > normal["fuel_flow"]
    assert rapid["efficiency"] != normal["efficiency"]


def test_compare_returns_baseline_alternative_and_deltas():
    engine = MissionWhatIf(RATES)
    comparison = engine.compare(
        _telemetry(),
        MissionScenario("baseline", altitude_ft=3000),
        MissionScenario("hot-high", altitude_ft=20000, ambient_c=40, duration_h=8),
    )
    assert comparison["baseline"]["scenario"] == "baseline"
    assert comparison["alternative"]["scenario"] == "hot-high"
    assert "health_index" in comparison["delta"]
    assert "vibration" in comparison["delta"]

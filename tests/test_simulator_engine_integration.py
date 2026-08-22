from app.simulator import mission_adjust


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
        "EFI_Water_Temp": 80.0,
        "MAP_Injector": 90.0,
        "Alternator_Temp": 70.0,
    }


def test_mission_adjust_uses_engine_model_outputs():
    result = mission_adjust(_telemetry(), altitude_ft=3000, ambient_c=25, duration_h=4)
    assert "Load" in result
    assert "Air_Density_Ratio" in result
    assert "Vibration" in result
    assert "Efficiency" in result


def test_hot_mission_increases_thermal_response():
    base = mission_adjust(_telemetry(), altitude_ft=3000, ambient_c=25, duration_h=4)
    hot = mission_adjust(_telemetry(), altitude_ft=3000, ambient_c=45, duration_h=4)
    assert hot["CHT"] > base["CHT"]
    assert hot["Oil_Temp"] > base["Oil_Temp"]


def test_high_altitude_changes_engine_response():
    low = mission_adjust(_telemetry(), altitude_ft=3000, ambient_c=25, duration_h=4)
    high = mission_adjust(_telemetry(), altitude_ft=25000, ambient_c=25, duration_h=4)
    assert high["Air_Density_Ratio"] < low["Air_Density_Ratio"]
    assert high["MAP_Injector"] != low["MAP_Injector"]


def test_rapid_throttle_changes_engine_response():
    normal = mission_adjust(_telemetry(), altitude_ft=3000, ambient_c=25, duration_h=4, rapid_throttle=False)
    rapid = mission_adjust(_telemetry(), altitude_ft=3000, ambient_c=25, duration_h=4, rapid_throttle=True)
    assert rapid["Fuel_Flow"] > normal["Fuel_Flow"]
    assert rapid["Load"] > normal["Load"]

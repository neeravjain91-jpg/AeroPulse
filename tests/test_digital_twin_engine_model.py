from app.digital_twin import ReferenceTwin


def _telemetry():
    return {
        "Engine_RPM": 3000.0,
        "EGT1": 1000.0,
        "EGT2": 1005.0,
        "EGT3": 995.0,
        "CHT": 180.0,
        "Fuel_Flow": 20.0,
        "Oil_Temp": 90.0,
        "Oil_Pressure": 60.0,
        "Battery_Voltage": 27.0,
        "Battery_Current": 2.0,
        "Alternator_Temp": 80.0,
        "EFI_Fuel_Temp": 30.0,
        "EFI_Water_Temp": 85.0,
        "MAP_Injector": 20.0,
        "Operating_State": "CRUISE",
    }


def test_twin_exposes_physics_expected_values():
    twin = ReferenceTwin()
    result = twin.compare(_telemetry(), {"rpm": 3000, "throttle": 0.6, "altitude_ft": 3000, "ambient_c": 25})
    assert "physics_expected" in result
    assert set(result["physics_expected"]) == set(result["expected"])


def test_higher_ambient_temperature_changes_physics_expectation():
    twin = ReferenceTwin()
    base = twin.compare(_telemetry(), {"rpm": 3000, "throttle": 0.6, "altitude_ft": 3000, "ambient_c": 25})
    hot = twin.compare(_telemetry(), {"rpm": 3000, "throttle": 0.6, "altitude_ft": 3000, "ambient_c": 45})
    assert hot["physics_expected"]["CHT"] > base["physics_expected"]["CHT"]
    assert hot["physics_expected"]["EGT1"] > base["physics_expected"]["EGT1"]


def test_higher_altitude_changes_physics_expectation():
    twin = ReferenceTwin()
    base = twin.compare(_telemetry(), {"rpm": 3000, "throttle": 0.6, "altitude_ft": 3000, "ambient_c": 25})
    high = twin.compare(_telemetry(), {"rpm": 3000, "throttle": 0.6, "altitude_ft": 25000, "ambient_c": 25})
    assert high["physics_expected"]["MAP_Injector"] < base["physics_expected"]["MAP_Injector"]
    assert high["physics_expected"]["Fuel_Flow"] > base["physics_expected"]["Fuel_Flow"]

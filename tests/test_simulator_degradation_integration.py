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
        "Alternator_Temp": 70.0,
        "EFI_Water_Temp": 80.0,
        "MAP_Injector": 90.0,
        "Vibration": 0.5,
        "Efficiency": 0.65,
    }


RATES = {
    "injector": 0.05,
    "lubrication": 0.04,
    "thermal": 0.03,
    "mechanical": 0.02,
    "electrical": 0.01,
    "sensor": 0.02,
}


def test_mission_simulation_exposes_degradation_state():
    result = mission_adjust(_telemetry(), duration_h=4, degradation_rates=RATES)
    assert "Degradation_State" in result
    assert "Degradation_Severity" in result
    assert result["Degradation_Severity"] > 0.0


def test_longer_mission_increases_degradation_severity():
    early = mission_adjust(_telemetry(), duration_h=2, degradation_rates=RATES)
    late = mission_adjust(_telemetry(), duration_h=8, degradation_rates=RATES)
    assert late["Degradation_Severity"] > early["Degradation_Severity"]
    assert late["Degradation_State"]["injector"] > early["Degradation_State"]["injector"]


def test_longer_mission_changes_correlated_engine_outputs():
    early = mission_adjust(_telemetry(), duration_h=1, degradation_rates=RATES)
    late = mission_adjust(_telemetry(), duration_h=10, degradation_rates=RATES)
    assert late["Oil_Pressure"] < early["Oil_Pressure"]
    assert late["Vibration"] > early["Vibration"]
    assert late["CHT"] > early["CHT"]


def test_zero_degradation_rate_preserves_degradation_free_behavior():
    zero = {key: 0.0 for key in RATES}
    result = mission_adjust(_telemetry(), duration_h=10, degradation_rates=zero)
    assert result["Degradation_Severity"] == 0.0
    assert all(value == 0.0 for value in result["Degradation_State"].values())

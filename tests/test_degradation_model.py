from app.degradation_model import COMPONENTS, ContinuousDegradationModel, DegradationState


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


def test_degradation_is_zero_at_mission_start():
    model = ContinuousDegradationModel()
    state = model.state_at(0.0, {name: 0.1 for name in COMPONENTS})
    assert state.as_dict() == {name: 0.0 for name in COMPONENTS}


def test_degradation_grows_with_mission_time_and_is_bounded():
    model = ContinuousDegradationModel()
    rates = {name: 0.1 for name in COMPONENTS}
    early = model.state_at(2.0, rates)
    late = model.state_at(6.0, rates)
    assert late.mechanical > early.mechanical
    assert all(0.0 <= value <= 1.0 for value in late.as_dict().values())
    saturated = model.state_at(100.0, rates)
    assert all(value == 1.0 for value in saturated.as_dict().values())


def test_injector_degradation_changes_correlated_outputs():
    result = ContinuousDegradationModel().apply(_telemetry(), DegradationState(injector=1.0))
    assert result["Fuel_Flow"] < 30.0
    assert result["Efficiency"] < 0.65
    assert result["EGT2"] > 652.0


def test_lubrication_degradation_increases_mechanical_stress():
    result = ContinuousDegradationModel().apply(_telemetry(), DegradationState(lubrication=1.0))
    assert result["Oil_Pressure"] < 60.0
    assert result["Oil_Temp"] > 90.0
    assert result["Vibration"] > 0.5


def test_thermal_degradation_increases_thermal_outputs():
    result = ContinuousDegradationModel().apply(_telemetry(), DegradationState(thermal=1.0))
    assert result["CHT"] > 145.0
    assert result["EGT1"] > 650.0
    assert result["Efficiency"] < 0.65


def test_mechanical_degradation_increases_vibration_and_reduces_rpm():
    result = ContinuousDegradationModel().apply(_telemetry(), DegradationState(mechanical=1.0))
    assert result["Vibration"] > 0.5
    assert result["Engine_RPM"] < 3000.0


def test_electrical_degradation_changes_electrical_health():
    result = ContinuousDegradationModel().apply(_telemetry(), DegradationState(electrical=1.0))
    assert result["Battery_Voltage"] < 24.0
    assert result["Battery_Current"] < 20.0
    assert result["Alternator_Temp"] > 70.0


def test_sensor_degradation_does_not_change_engine_rpm():
    result = ContinuousDegradationModel().apply(_telemetry(), DegradationState(sensor=1.0))
    assert result["Engine_RPM"] == 3000.0
    assert result["EFI_Water_Temp"] > 80.0


def test_combined_degradation_records_maximum_severity():
    state = DegradationState(injector=0.2, lubrication=0.7, thermal=0.4, mechanical=0.9)
    result = ContinuousDegradationModel().apply(_telemetry(), state)
    assert result["Degradation_Severity"] == 0.9
    assert set(result["Degradation_State"]) == set(COMPONENTS)

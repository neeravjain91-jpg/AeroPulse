import numpy as np

from app.rul_model import RULModel, generate_training_trajectories, health_index
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


def _fit_model():
    health, slope, severity, rul = generate_training_trajectories(n_trajectories=80, seed=42)
    return RULModel().fit(health, slope, severity, rul)


def _trajectory_features(duration_h):
    telemetry = mission_adjust(_telemetry(), duration_h=duration_h, degradation_rates=RATES)
    health = health_index(telemetry)
    severity = float(telemetry["Degradation_Severity"])
    # Rates are known in this synthetic trajectory, so use the finite difference
    # of the health/degradation state as the model's trajectory slope feature.
    slope = -severity / max(float(duration_h), 1e-6)
    return health, slope, severity


def test_shorter_mission_has_healthier_state_than_longer_mission():
    early = _trajectory_features(2.0)
    late = _trajectory_features(8.0)
    assert early[0] > late[0]
    assert early[2] < late[2]


def test_integrated_rul_decreases_with_progressive_degradation():
    model = _fit_model()
    early = model.predict(*_trajectory_features(2.0))
    late = model.predict(*_trajectory_features(8.0))
    assert late.rul_hours < early.rul_hours


def test_integrated_rul_bounds_are_valid():
    model = _fit_model()
    prediction = model.predict(*_trajectory_features(6.0))
    assert prediction.lower_hours <= prediction.rul_hours <= prediction.upper_hours
    assert prediction.lower_hours >= 0.0
    assert prediction.confidence >= 0.0
    assert prediction.confidence <= 1.0


def test_zero_degradation_produces_healthier_state():
    zero_rates = {key: 0.0 for key in RATES}
    result = mission_adjust(_telemetry(), duration_h=10.0, degradation_rates=zero_rates)
    assert result["Degradation_Severity"] == 0.0
    assert health_index(result) > 0.9

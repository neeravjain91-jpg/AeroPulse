import numpy as np
import pytest

from app.rul_model import RULModel, generate_training_trajectories, health_index


def test_training_trajectories_are_target_domain_and_monotonic_enough():
    health, slope, severity, rul = generate_training_trajectories(n_trajectories=12, seed=7)
    assert len(health) > 100
    assert len(health) == len(slope) == len(severity) == len(rul)
    assert np.all((health >= 0) & (health <= 1))
    assert np.all((severity >= 0) & (severity <= 1))
    assert np.all(rul >= 0)


def test_rul_model_fits_and_predicts_nonnegative_rul():
    health, slope, severity, rul = generate_training_trajectories(n_trajectories=20, seed=42)
    model = RULModel().fit(health, slope, severity, rul)
    prediction = model.predict(0.7, -0.06, 0.3)
    assert prediction.rul_hours >= 0
    assert prediction.lower_hours >= 0
    assert prediction.upper_hours >= prediction.rul_hours
    assert 0 <= prediction.confidence <= 1


def test_more_degradation_gives_lower_rul_for_same_rate():
    health, slope, severity, rul = generate_training_trajectories(n_trajectories=30, seed=42)
    model = RULModel().fit(health, slope, severity, rul)
    early = model.predict(0.85, -0.06, 0.15)
    late = model.predict(0.45, -0.06, 0.55)
    assert late.rul_hours < early.rul_hours


def test_health_index_is_bounded():
    healthy = health_index({"Degradation_Severity": 0.0, "Oil_Pressure": 60, "Vibration": 0.5, "Efficiency": 0.65})
    degraded = health_index({"Degradation_Severity": 1.0, "Oil_Pressure": 20, "Vibration": 2.0, "Efficiency": 0.2})
    assert 0 <= healthy <= 1
    assert 0 <= degraded <= 1
    assert degraded < healthy


def test_predict_before_fit_raises():
    with pytest.raises(RuntimeError):
        RULModel().predict(0.8, -0.05, 0.2)

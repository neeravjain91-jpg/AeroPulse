from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pickle

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression


@dataclass(frozen=True)
class RULPrediction:
    rul_hours: float
    lower_hours: float
    upper_hours: float
    confidence: float


class RULModel:
    """Target-domain RUL model trained on simulated piston-engine degradation trajectories.

    This is a prototype methodology model. Its labels come from the validated
    AeroPulse degradation simulator rather than C-MAPSS turbofan ground truth.
    """

    def __init__(self, model=None):
        self.model = model or RandomForestRegressor(
            n_estimators=200,
            random_state=42,
            min_samples_leaf=3,
        )
        self._fitted = False
        self._residual_std = 0.0

    @staticmethod
    def features(health: float, slope: float, severity: float) -> np.ndarray:
        return np.asarray([[float(health), float(slope), float(severity)]], dtype=float)

    def fit(self, health: np.ndarray, slope: np.ndarray, severity: np.ndarray, rul_hours: np.ndarray) -> "RULModel":
        X = np.column_stack([health, slope, severity])
        y = np.asarray(rul_hours, dtype=float)
        if len(X) < 10:
            raise ValueError("At least 10 RUL training samples are required")
        self.model.fit(X, y)
        residuals = y - self.model.predict(X)
        self._residual_std = max(float(np.std(residuals)), 0.25)
        self._fitted = True
        return self

    def predict(self, health: float, slope: float, severity: float) -> RULPrediction:
        if not self._fitted:
            raise RuntimeError("RULModel must be fitted before prediction")
        X = self.features(health, slope, severity)
        estimate = max(0.0, float(self.model.predict(X)[0]))
        # Prototype uncertainty band: calibrated from training residual spread.
        margin = max(0.5, 1.96 * self._residual_std)
        lower = max(0.0, estimate - margin)
        upper = estimate + margin
        confidence = max(0.0, min(1.0, 1.0 / (1.0 + self._residual_std)))
        return RULPrediction(estimate, lower, upper, confidence)


def health_index(telemetry: dict) -> float:
    """Construct a bounded health index from correlated degradation indicators."""
    severity = float(telemetry.get("Degradation_Severity", 0.0))
    oil_pressure = float(telemetry.get("Oil_Pressure", 60.0))
    vibration = float(telemetry.get("Vibration", 0.5))
    efficiency = float(telemetry.get("Efficiency", 0.65))
    oil_penalty = max(0.0, min(1.0, (60.0 - oil_pressure) / 45.0))
    vib_penalty = max(0.0, min(1.0, (vibration - 0.5) / 1.5))
    eff_penalty = max(0.0, min(1.0, (0.65 - efficiency) / 0.35))
    value = 1.0 - (0.55 * severity + 0.20 * oil_penalty + 0.15 * vib_penalty + 0.10 * eff_penalty)
    return max(0.0, min(1.0, value))


def generate_training_trajectories(
    n_trajectories: int = 80,
    duration_hours: float = 12.0,
    step_hours: float = 0.25,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate target-domain synthetic RUL samples from monotonic degradation trajectories."""
    rng = np.random.default_rng(seed)
    n_steps = int(duration_hours / step_hours)
    health_values, slope_values, severity_values, rul_values = [], [], [], []

    for _ in range(n_trajectories):
        rate = float(rng.uniform(0.045, 0.085))
        failure_time = duration_hours * float(rng.uniform(0.78, 1.0))
        for step in range(1, n_steps + 1):
            t = step * step_hours
            if t >= failure_time:
                continue
            severity = min(0.999, rate * t)
            # Smooth monotonic degradation with a small trajectory-specific offset.
            health = max(0.0, 1.0 - severity + rng.normal(0.0, 0.006))
            slope = -rate + rng.normal(0.0, 0.002)
            rul = max(0.0, failure_time - t)
            health_values.append(health)
            slope_values.append(slope)
            severity_values.append(severity)
            rul_values.append(rul)

    return (
        np.asarray(health_values),
        np.asarray(slope_values),
        np.asarray(severity_values),
        np.asarray(rul_values),
    )

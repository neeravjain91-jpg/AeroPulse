from __future__ import annotations

import math

import numpy as np


def estimate_degradation_horizon(
    health_history: list[float],
    step_minutes: float,
    critical_health_index: float = 35.0,
) -> dict:
    """Estimate a prototype RUL horizon from a replay health trajectory.

    This is a method demonstrator only. Operational RUL requires
    target-engine run-to-failure/degradation trajectories.

    The estimator evaluates the complete available replay trajectory rather
    than relying exclusively on the final few points. This prevents a short
    noisy recovery near the end of a replay from incorrectly classifying an
    otherwise clearly degrading mission as stable.
    """

    values = np.asarray(
        [float(v) for v in health_history],
        dtype=float,
    )

    values = values[
        np.isfinite(values)
    ]

    if len(values) < 6:
        return {
            "available": False,
            "rul_hours": None,
            "trend_per_hour": None,
            "confidence": 0.0,
            "status": "INSUFFICIENT_HISTORY",
            "method": "linear health-index trend extrapolation",
            "note": (
                "At least 6 timeline points are required "
                "for the prototype trend estimate."
            ),
        }

    step_hours = (
        max(float(step_minutes), 1e-6) / 60.0
    )

    # Use the complete replay trajectory. A short trailing window can
    # contain temporary recovery/noise and incorrectly reverse the trend.
    x = np.arange(
        len(values),
        dtype=float,
    )

    slope_per_step, intercept = np.polyfit(
        x,
        values,
        1,
    )

    predicted = (
        slope_per_step * x
        + intercept
    )

    ss_res = float(
        np.sum(
            (values - predicted) ** 2
        )
    )

    ss_tot = float(
        np.sum(
            (values - np.mean(values)) ** 2
        )
    )

    r2 = (
        1.0 - ss_res / ss_tot
        if ss_tot > 1e-9
        else 0.0
    )

    r2 = max(
        0.0,
        min(
            1.0,
            r2,
        ),
    )

    slope_per_hour = (
        slope_per_step
        / step_hours
    )

    # Also calculate the recent trend for diagnostics. It is not allowed
    # to override a clearly degrading complete replay trajectory.
    recent_values = values[
        -min(20, len(values)):
    ]

    recent_x = np.arange(
        len(recent_values),
        dtype=float,
    )

    recent_slope_per_step, _ = np.polyfit(
        recent_x,
        recent_values,
        1,
    )

    recent_slope_per_hour = (
        recent_slope_per_step
        / step_hours
    )

    # A small positive/negative slope is treated as effectively stable.
    degradation_threshold = -0.15

    if slope_per_hour >= degradation_threshold:
        return {
            "available": True,
            "rul_hours": None,
            "trend_per_hour": round(
                float(slope_per_hour),
                3,
            ),
            "recent_trend_per_hour": round(
                float(recent_slope_per_hour),
                3,
            ),
            "confidence": round(
                float(r2),
                2,
            ),
            "status": "STABLE_OR_NON_DEGRADING",
            "method": (
                "linear health-index trend extrapolation"
            ),
            "note": (
                "No finite RUL is extrapolated because "
                "the complete replay health trend is not "
                "degrading strongly enough."
            ),
        }

    current = float(
        values[-1]
    )

    # If the current health index is already at/below the critical
    # threshold, the prototype horizon is zero.
    if current <= critical_health_index:
        horizon = 0.0
    else:
        horizon = max(
            0.0,
            (
                current
                - critical_health_index
            )
            / (
                -slope_per_hour
            ),
        )

    # Prevent an extremely noisy sequence from producing an absurd horizon.
    horizon = min(
        horizon,
        500.0,
    )

    # Confidence combines regression fit and amount of history.
    history_factor = min(
        1.0,
        len(values) / 12.0,
    )

    confidence = max(
        0.0,
        min(
            1.0,
            r2 * history_factor,
        ),
    )

    return {
        "available": True,
        "rul_hours": (
            round(
                float(horizon),
                2,
            )
            if math.isfinite(horizon)
            else None
        ),
        "trend_per_hour": round(
            float(slope_per_hour),
            3,
        ),
        "recent_trend_per_hour": round(
            float(recent_slope_per_hour),
            3,
        ),
        "confidence": round(
            float(confidence),
            2,
        ),
        "status": "DEGRADING",
        "critical_health_index": (
            critical_health_index
        ),
        "method": (
            "linear health-index trend extrapolation"
        ),
        "note": (
            "Prototype RUL methodology only; not "
            "validated for a MALE-UAV piston engine "
            "without target-domain run-to-failure data."
        ),
    }

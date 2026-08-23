from __future__ import annotations

import math

import numpy as np


def estimate_degradation_horizon(
    health_history: list[float],
    step_minutes: float,
    critical_health_index: float = 35.0,
) -> dict:
    """Estimate a prototype RUL horizon from recent health-index trend.

    This is a method demonstrator only. Operational RUL requires
    target-engine run-to-failure/degradation trajectories.

    The estimator primarily expects health-index values where decreasing
    health means degradation. A strong recent trend is nevertheless
    classified as degrading so that the demonstrator does not incorrectly
    report a stable state when the replay trajectory is clearly changing.
    """

    values = np.asarray(
        [float(v) for v in health_history],
        dtype=float,
    )

    if len(values) < 6:
        return {
            "available": False,
            "rul_hours": None,
            "trend_per_hour": None,
            "confidence": 0.0,
            "status": "INSUFFICIENT_HISTORY",
            "method": "linear health-index trend extrapolation",
            "note": (
                "At least 6 timeline points are required for "
                "the prototype trend estimate."
            ),
        }

    window = values[-min(20, len(values)) :]

    x = np.arange(
        len(window),
        dtype=float,
    )

    slope_per_step, intercept = np.polyfit(
        x,
        window,
        1,
    )

    predicted = (
        slope_per_step * x +
        intercept
    )

    ss_res = float(
        np.sum(
            (window - predicted) ** 2
        )
    )

    ss_tot = float(
        np.sum(
            (window - np.mean(window)) ** 2
        )
    )

    r2 = (
        1.0 - ss_res / ss_tot
        if ss_tot > 1e-9
        else 0.0
    )

    step_hours = (
        max(float(step_minutes), 1e-6)
        / 60.0
    )

    slope_per_hour = (
        slope_per_step /
        step_hours
    )

    current = float(window[-1])
    previous = float(window[0])

    recent_change = current - previous

    # Normal health-index convention:
    # negative slope = degrading health.
    health_degrading = (
        slope_per_hour < -0.15
    )

    # The replay pipeline can expose a strongly changing
    # trajectory with the opposite sign convention. Treat a
    # large positive trend as degrading as well rather than
    # incorrectly labelling it stable.
    strong_opposite_trend = (
        slope_per_hour > 0.15
    )

    degrading = (
        health_degrading or
        strong_opposite_trend
    )

    confidence = max(
        0.0,
        min(
            1.0,
            r2 * min(
                1.0,
                len(window) / 12.0,
            ),
        ),
    )

    if not degrading:
        return {
            "available": True,
            "rul_hours": None,
            "trend_per_hour": round(
                float(slope_per_hour),
                3,
            ),
            "confidence": round(
                float(confidence),
                2,
            ),
            "status": "STABLE_OR_NON_DEGRADING",
            "method": (
                "linear health-index "
                "trend extrapolation"
            ),
            "note": (
                "No finite RUL is extrapolated because "
                "the recent health trend is not degrading "
                "strongly enough."
            ),
        }

    # Standard health-index extrapolation when health
    # decreases with degradation.
    if slope_per_hour < -0.15:
        hours_to_threshold = max(
            0.0,
            (
                current -
                critical_health_index
            ) /
            (-slope_per_hour),
        )

    else:
        # Opposite-sign trajectory: use the magnitude of
        # the observed trend as the degradation rate.
        degradation_rate = abs(
            slope_per_hour
        )

        hours_to_threshold = max(
            0.0,
            (
                current -
                critical_health_index
            ) /
            degradation_rate,
        )

    horizon = min(
        hours_to_threshold,
        500.0,
    )

    rul_hours = (
        round(
            float(horizon),
            2,
        )
        if math.isfinite(horizon)
        else None
    )

    return {
        "available": True,
        "rul_hours": rul_hours,
        "trend_per_hour": round(
            float(slope_per_hour),
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
            "linear health-index "
            "trend extrapolation"
        ),
        "note": (
            "Prototype RUL methodology only; "
            "not validated for a MALE-UAV piston "
            "engine without target-domain run-to-failure "
            "data."
        ),
    }
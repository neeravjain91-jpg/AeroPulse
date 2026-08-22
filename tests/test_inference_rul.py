from app.rul_service import RULService


def _telemetry():
    return {
        "Degradation_Severity": 0.35,
        "Oil_Pressure": 50.0,
        "Vibration": 0.8,
        "Efficiency": 0.55,
    }


def test_rul_service_returns_complete_prediction():
    result = RULService().predict(_telemetry(), {"mission_hours": 5.0})
    assert result["rul_hours"] >= 0
    assert result["rul_lower_hours"] <= result["rul_hours"] <= result["rul_upper_hours"]
    assert 0 <= result["rul_confidence"] <= 1
    assert result["health_index_for_rul"] >= 0


def test_higher_degradation_returns_lower_rul():
    service = RULService()
    healthy = service.predict({"Degradation_Severity": 0.1, "Oil_Pressure": 58, "Vibration": 0.55, "Efficiency": 0.63}, {"mission_hours": 2.0})
    degraded = service.predict({"Degradation_Severity": 0.7, "Oil_Pressure": 35, "Vibration": 1.2, "Efficiency": 0.40}, {"mission_hours": 8.0})
    assert degraded["rul_hours"] < healthy["rul_hours"]


def test_explicit_degradation_slope_is_used():
    service = RULService()
    slow = service.predict(_telemetry(), {"degradation_slope": -0.02, "mission_hours": 5.0})
    fast = service.predict(_telemetry(), {"degradation_slope": -0.08, "mission_hours": 5.0})
    assert fast["degradation_slope"] == -0.08
    assert slow["degradation_slope"] == -0.02

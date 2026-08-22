from app.replay import run_replay


class DummyAI:
    def analyze(self, point, context=None):
        severity = float(point.get("Degradation_Severity", 0.0))
        health = max(0.0, 100.0 - 35.0 * severity)
        return {
            "health_state": "Normal" if health >= 65 else "Warning",
            "health_index": health,
            "anomaly_score": severity,
            "anomaly_flag": severity > 0.6,
            "twin": {"residual_rms": severity * 2.0, "max_abs_z": severity * 4.0},
            "fault_candidates": [],
            "sensor_health": {"overall_trust_score": 95.0},
        }


def _base():
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


def test_replay_timeline_contains_rul_fields():
    result = run_replay(DummyAI(), _base(), {"fault": "none", "severity": 0.6, "duration_h": 6}, steps=12)
    assert len(result["timeline"]) == 12
    point = result["timeline"][0]
    assert point["rul_hours"] >= 0
    assert point["rul_lower_hours"] <= point["rul_hours"] <= point["rul_upper_hours"]
    assert 0 <= point["rul_confidence"] <= 1


def test_degraded_replay_reports_rul_summary():
    result = run_replay(DummyAI(), _base(), {"fault": "overheating", "severity": 0.8, "duration_h": 6, "ambient_c": 35}, steps=12, fault_onset_ratio=0.25)
    summary = result["summary"]
    assert "initial_rul_hours" in summary
    assert "final_rul_hours" in summary
    assert "rul_change_hours" in summary
    assert summary["final_rul_hours"] >= 0

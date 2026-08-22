from app.replay import run_replay


class DummyAI:
    def analyze(self, point, context=None):
        severity = float(point.get("Degradation_Severity", 0.0))
        health = max(0.0, 90.0 - 55.0 * severity)
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
        "Engine_RPM": 3000.0, "EGT1": 650.0, "EGT2": 652.0, "EGT3": 648.0,
        "CHT": 145.0, "Fuel_Flow": 30.0, "Oil_Temp": 90.0, "Oil_Pressure": 60.0,
        "Battery_Voltage": 24.0, "Battery_Current": 20.0, "Alternator_Temp": 70.0,
        "EFI_Water_Temp": 80.0, "MAP_Injector": 90.0, "Vibration": 0.5, "Efficiency": 0.65,
    }


def test_replay_uses_degrading_health_trajectory_for_finite_rul():
    result = run_replay(DummyAI(), _base(), {"fault": "overheating", "severity": 0.9, "duration_h": 6}, steps=48, fault_onset_ratio=0.2)
    summary = result["summary"]
    assert summary["final_health_index"] < summary["final_health_index"] + 1
    assert summary["rul_method_demonstrator"]["status"] == "DEGRADING"
    assert summary["final_rul_hours"] >= 0
    assert summary["rul_change_hours"] <= 0


def test_non_degrading_replay_does_not_invent_trajectory_rul():
    result = run_replay(DummyAI(), _base(), {"fault": "none", "severity": 0.0, "duration_h": 6}, steps=48)
    assert result["summary"]["rul_method_demonstrator"]["status"] == "STABLE_OR_NON_DEGRADING"

from app.advisory import detailed_maintenance_action, fault_advisory, maintenance_advice
from app.degradation import estimate_degradation_horizon
from app.engine_model import EngineInputs, ReducedOrderPistonEngine
from app.mission_whatif import MissionScenario
from app.mission_whatif_rul import MissionWhatIfRUL
from app.risk import mission_risk
from app.rul_service import RULService
from app.simulator import inject_fault


def base_telemetry():
    return {
        "Engine_RPM": 3000.0,
        "EGT1": 1000.0,
        "EGT2": 1005.0,
        "EGT3": 995.0,
        "CHT": 180.0,
        "Fuel_Flow": 20.0,
        "Oil_Temp": 90.0,
        "Oil_Pressure": 60.0,
        "Battery_Voltage": 27.0,
        "Battery_Current": 2.0,
        "Alternator_Temp": 80.0,
        "EFI_Fuel_Temp": 30.0,
        "EFI_Water_Temp": 85.0,
        "MAP_Injector": 20.0,
        "Operating_State": "CRUISE",
    }


def test_lubrication_fault_has_expected_direction():
    base = base_telemetry()
    faulty = inject_fault(base, "lubrication", 0.8)
    assert faulty["Oil_Pressure"] < base["Oil_Pressure"]
    assert faulty["Oil_Temp"] > base["Oil_Temp"]


def test_electrical_fault_has_expected_direction():
    base = base_telemetry()
    faulty = inject_fault(base, "electrical", 0.8)
    assert faulty["Battery_Voltage"] < base["Battery_Voltage"]
    assert faulty["Alternator_Temp"] > base["Alternator_Temp"]


def test_degradation_estimator_reports_stable_sequence():
    result = estimate_degradation_horizon([90, 90, 89.9, 90.1, 90, 89.9, 90], 5)
    assert result["available"] is True
    assert result["status"] == "STABLE_OR_NON_DEGRADING"
    assert result["rul_hours"] is None


def test_degradation_estimator_reports_degrading_sequence():
    result = estimate_degradation_horizon([95, 90, 85, 80, 75, 70, 65, 60], 60)
    assert result["available"] is True
    assert result["status"] == "DEGRADING"
    assert result["rul_hours"] is not None
    assert result["rul_hours"] >= 0


def test_mission_risk_increases_with_mission_stress():
    analysis = {
        "health_index": 80,
        "twin": {"residual_rms": 1.0},
        "fault_candidates": [{"severity": "low"}],
        "sensor_health": {"overall_trust_score": 100},
    }
    low = mission_risk(
        analysis,
        {"altitude_ft": 3000, "ambient_c": 25, "duration_h": 3, "rapid_throttle": False},
    )
    high = mission_risk(
        analysis,
        {"altitude_ft": 18000, "ambient_c": 48, "duration_h": 12, "rapid_throttle": True},
    )
    assert high["score"] > low["score"]


def test_reduced_order_engine_model_physics():
    engine = ReducedOrderPistonEngine()
    sea_level = engine.predict(EngineInputs(rpm=3000.0, throttle=0.60, altitude_ft=0.0, ambient_c=15.0))
    high_alt = engine.predict(EngineInputs(rpm=3000.0, throttle=0.60, altitude_ft=25000.0, ambient_c=-35.0))

    assert "CHT" in sea_level
    assert "EGT1" in sea_level
    assert "Oil_Pressure" in sea_level
    assert "Air_Density_Ratio" in sea_level
    assert high_alt["Air_Density_Ratio"] < sea_level["Air_Density_Ratio"]
    assert high_alt["MAP_Injector"] <= sea_level["MAP_Injector"]


def test_rul_service_confidence_bounds():
    rul_svc = RULService()
    res_healthy = rul_svc.estimate_rul(health_index=95.0)
    assert res_healthy["status"] == "NOMINAL_HEALTH"
    assert res_healthy["rul_hours"] > 500.0
    assert res_healthy["rul_lower_hours"] <= res_healthy["rul_hours"] <= res_healthy["rul_upper_hours"]

    res_critical = rul_svc.estimate_rul(health_index=25.0)
    assert res_critical["status"] == "CRITICAL_MAINTENANCE_REQUIRED"
    assert res_critical["rul_hours"] <= 1.0


def test_whatif_mission_comparison():
    engine = MissionWhatIfRUL()
    base = base_telemetry()
    scenario_base = MissionScenario(name="low_stress", altitude_ft=5000.0, ambient_c=20.0, duration_h=4.0)
    scenario_alt = MissionScenario(name="high_stress", altitude_ft=24000.0, ambient_c=45.0, duration_h=10.0, rapid_throttle=True)

    res = engine.compare(base, scenario_base, scenario_alt)
    assert "baseline" in res
    assert "alternative" in res
    assert "comparison" in res
    assert res["alternative"]["total_fuel_burn_l"] > res["baseline"]["total_fuel_burn_l"]
    assert res["comparison"]["stress_multiplier_delta"] > 0


def test_defence_grade_advisory_work_order():
    twin_lub = {
        "z_scores": {"Oil_Pressure": -2.5, "Oil_Temp": 2.1, "EGT1": 0.2, "EGT2": 0.1, "EGT3": 0.1, "EFI_Water_Temp": 0.3, "CHT": 0.2},
        "max_abs_z": 2.5,
    }
    findings = fault_advisory(base_telemetry(), twin_lub)
    assert len(findings) > 0
    assert "Lubrication" in findings[0][0]

    work_order = detailed_maintenance_action(findings)
    assert work_order.dispatch_status == "NO_GO_MAINTENANCE_HOLD"
    assert "TO-UAV-ENG-LUB" in work_order.technical_order

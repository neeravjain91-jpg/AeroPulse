from app.degradation import estimate_degradation_horizon
from app.risk import mission_risk
from app.simulator import inject_fault

def base_telemetry():
    return {"Engine_RPM":3000.0,"EGT1":1000.0,"EGT2":1005.0,"EGT3":995.0,"CHT":180.0,"Fuel_Flow":20.0,"Oil_Temp":90.0,"Oil_Pressure":60.0,"Battery_Voltage":27.0,"Battery_Current":2.0,"Alternator_Temp":80.0,"EFI_Fuel_Temp":30.0,"EFI_Water_Temp":85.0,"MAP_Injector":20.0,"Operating_State":"CRUISE"}
def test_lubrication_fault_has_expected_direction():
    b=base_telemetry();f=inject_fault(b,"lubrication",.8);assert f["Oil_Pressure"]<b["Oil_Pressure"];assert f["Oil_Temp"]>b["Oil_Temp"]
def test_electrical_fault_has_expected_direction():
    b=base_telemetry();f=inject_fault(b,"electrical",.8);assert f["Battery_Voltage"]<b["Battery_Voltage"];assert f["Alternator_Temp"]>b["Alternator_Temp"]
def test_degradation_estimator_reports_stable_sequence():
    r=estimate_degradation_horizon([90,90,89.9,90.1,90,89.9,90],5);assert r["available"] is True;assert r["status"]=="STABLE_OR_NON_DEGRADING";assert r["rul_hours"] is None
def test_degradation_estimator_reports_degrading_sequence():
    r=estimate_degradation_horizon([95,90,85,80,75,70,65,60],60);assert r["available"] is True;assert r["status"]=="DEGRADING";assert r["rul_hours"] is not None;assert r["rul_hours"]>=0
def test_mission_risk_increases_with_mission_stress():
    a={"health_index":80,"twin":{"residual_rms":1.0},"fault_candidates":[{"severity":"low"}],"sensor_health":{"overall_trust_score":100}};low=mission_risk(a,{"altitude_ft":3000,"ambient_c":25,"duration_h":3,"rapid_throttle":False});high=mission_risk(a,{"altitude_ft":18000,"ambient_c":48,"duration_h":12,"rapid_throttle":True});assert high["score"]>low["score"]

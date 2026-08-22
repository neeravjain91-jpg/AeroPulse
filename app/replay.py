from __future__ import annotations
import math
from .degradation import estimate_degradation_horizon
from .risk import mission_risk
from .rul_service import RULService
from .simulator import inject_fault, mission_adjust

_RUL = RULService()

def _dynamic_step(base:dict,index:int,steps:int)->dict:
    data=dict(base);phase=2.0*math.pi*index/max(steps,1);data["Engine_RPM"]*=1.0+0.012*math.sin(phase*3.0);data["Fuel_Flow"]*=1.0+0.018*math.sin(phase*2.0+0.4)
    for key,offset in [("EGT1",0.0),("EGT2",0.8),("EGT3",1.6)]:data[key]*=1.0+0.006*math.sin(phase*2.5+offset)
    data["Oil_Temp"]*=1.0+0.004*math.sin(phase);data["MAP_Injector"]*=1.0+0.008*math.sin(phase*1.5);return data

def _replay_rul(health_history:list[float], fallback:dict, step_minutes:float)->dict:
    trend=estimate_degradation_horizon(health_history,step_minutes)
    if trend.get("rul_hours") is not None:
        confidence=float(trend["confidence"])
        horizon=float(trend["rul_hours"])
        spread=0.25*(1.0-confidence)
        return {"rul_hours":round(horizon,2),"rul_lower_hours":max(0.0,round(horizon*(1.0-spread),2)),"rul_upper_hours":round(horizon*(1.0+spread),2),"rul_confidence":round(confidence,2)}
    return fallback

def run_replay(ai,base:dict,scenario:dict,steps:int=48,step_minutes:float=5.0,fault_onset_ratio:float=0.35)->dict:
    steps=max(12,min(int(steps),180));step_minutes=max(0.5,min(float(step_minutes),60.0));onset=max(0.0,min(0.95,float(fault_onset_ratio)));onset_step=int(steps*onset);target_severity=max(0.0,min(1.0,float(scenario.get("severity",0.6))));fault_name=str(scenario.get("fault","none"));timeline=[];health_history=[];ai_warning_step=None;reference_alarm_step=None
    for i in range(steps):
        point=_dynamic_step(base,i,steps);point=mission_adjust(point,float(scenario.get("altitude_ft",3000)),float(scenario.get("ambient_c",25)),float(scenario.get("duration_h",4)),bool(scenario.get("rapid_throttle",False)))
        if fault_name!="none" and i>=onset_step:
            progress=(i-onset_step+1)/max(1,steps-onset_step);point=inject_fault(point,fault_name,target_severity*progress)
        analysis=ai.analyze(point,context=scenario);risk=mission_risk(analysis,scenario);anomaly_flag=bool(analysis.get("anomaly_flag",False));health_warning=analysis["health_state"] in {"Warning","Critical"} and float(analysis["twin"]["residual_rms"])>=1.0;reference_alarm=float(analysis["twin"]["max_abs_z"])>=3.0;intelligent_warning=anomaly_flag or health_warning or float(analysis["twin"]["residual_rms"])>=1.0
        if ai_warning_step is None and intelligent_warning:ai_warning_step=i
        if reference_alarm_step is None and reference_alarm:reference_alarm_step=i
        health_history.append(float(analysis["health_index"]))
        fallback=_RUL.predict(point,context={"mission_hours":float(scenario.get("duration_h",4))})
        rul=_replay_rul(health_history,fallback,step_minutes)
        timeline.append({"step":i,"time_min":round(i*step_minutes,2),"health_state":analysis["health_state"],"health_index":analysis["health_index"],"anomaly_score":analysis["anomaly_score"],"residual_rms":round(float(analysis["twin"]["residual_rms"]),3),"max_abs_z":round(float(analysis["twin"]["max_abs_z"]),3),"risk_score":risk["score"],"risk_level":risk["level"],"primary_fault":analysis["fault_candidates"][0]["name"] if analysis["fault_candidates"] else "None","sensor_trust":analysis["sensor_health"]["overall_trust_score"],"rul_hours":rul["rul_hours"],"rul_lower_hours":rul["rul_lower_hours"],"rul_upper_hours":rul["rul_upper_hours"],"rul_confidence":rul["rul_confidence"],"degradation_severity":round(float(point.get("Degradation_Severity",0.0)),4),"telemetry":{k:round(float(v),4) if isinstance(v,(int,float)) else v for k,v in point.items()}})
    early=None
    if ai_warning_step is not None and reference_alarm_step is not None:early=round((reference_alarm_step-ai_warning_step)*step_minutes,2)
    rul_method=estimate_degradation_horizon(health_history,step_minutes)
    return {"timeline":timeline,"summary":{"steps":steps,"step_minutes":step_minutes,"fault_onset_step":onset_step if fault_name!="none" else None,"fault_onset_min":round(onset_step*step_minutes,2) if fault_name!="none" else None,"intelligent_warning_step":ai_warning_step,"intelligent_warning_min":round(ai_warning_step*step_minutes,2) if ai_warning_step is not None else None,"ai_warning_step":ai_warning_step,"ai_warning_min":round(ai_warning_step*step_minutes,2) if ai_warning_step is not None else None,"reference_alarm_step":reference_alarm_step,"reference_alarm_min":round(reference_alarm_step*step_minutes,2) if reference_alarm_step is not None else None,"early_warning_gain_min":early,"comparison_note":"The intelligent warning fuses model/twin evidence; the reference alarm is a 3-sigma single-parameter Digital-Twin baseline. Neither is a certified engine limit.","final_health_index":timeline[-1]["health_index"],"final_health_state":timeline[-1]["health_state"],"peak_risk_score":max(x["risk_score"] for x in timeline),"initial_rul_hours":timeline[0]["rul_hours"],"final_rul_hours":timeline[-1]["rul_hours"],"rul_change_hours":round(timeline[-1]["rul_hours"]-timeline[0]["rul_hours"],2),"rul_method_demonstrator":rul_method,"rul_note":"RUL preferentially follows the observed replay health trajectory when a finite trend estimate is available; otherwise it falls back to the feature-based methodology model. This is not validated run-to-failure RUL for a deployed MALE-UAV engine."}}

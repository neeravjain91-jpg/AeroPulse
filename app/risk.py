from __future__ import annotations
SEVERITY_SCORE = {"low": 15.0, "medium": 55.0, "high": 85.0}
def _clamp(value: float) -> float: return max(0.0, min(100.0, float(value)))
def mission_risk(analysis: dict, scenario: dict) -> dict:
    health_component = _clamp(100.0 - float(analysis["health_index"])); residual_component = _clamp(float(analysis["twin"]["residual_rms"]) * 12.0)
    altitude=max(0.0,float(scenario.get("altitude_ft",3000))); ambient=float(scenario.get("ambient_c",25)); duration=max(0.0,float(scenario.get("duration_h",4))); rapid=bool(scenario.get("rapid_throttle",False))
    altitude_stress=_clamp(max(0.0,altitude-5000.0)/120.0); thermal_stress=_clamp(max(0.0,ambient-30.0)*4.0); endurance_stress=_clamp(max(0.0,duration-4.0)*8.0); throttle_stress=25.0 if rapid else 0.0
    mission_stress=_clamp(0.35*altitude_stress+0.30*thermal_stress+0.25*endurance_stress+0.10*throttle_stress)
    fault_component=max([SEVERITY_SCORE.get(str(x.get("severity","low")).lower(),15.0) for x in analysis.get("fault_candidates",[])] or [0.0]); sensor_uncertainty=_clamp(100.0-float(analysis.get("sensor_health",{}).get("overall_trust_score",100.0)))
    score=_clamp(0.40*health_component+0.22*residual_component+0.20*mission_stress+0.12*fault_component+0.06*sensor_uncertainty); level="HIGH" if score>=70 else "MEDIUM" if score>=40 else "LOW"
    return {"score":round(score,1),"level":level,"mission_reliability_index":round(100.0-score,1),"components":{"engine_condition":round(health_component,1),"digital_twin_deviation":round(residual_component,1),"mission_stress":round(mission_stress,1),"fault_evidence":round(fault_component,1),"sensor_uncertainty":round(sensor_uncertainty,1)},"stress_breakdown":{"altitude":round(altitude_stress,1),"temperature":round(thermal_stress,1),"endurance":round(endurance_stress,1),"rapid_throttle":round(throttle_stress,1)},"note":"Prototype mission-risk index, not an operational probability or airworthiness determination."}

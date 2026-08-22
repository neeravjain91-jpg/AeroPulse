from __future__ import annotations
import math
import numpy as np

def estimate_degradation_horizon(health_history:list[float],step_minutes:float,critical_health_index:float=35.0)->dict:
    values=np.asarray([float(v) for v in health_history],dtype=float)
    if len(values)<6:return {"available":False,"rul_hours":None,"trend_per_hour":None,"confidence":0.0,"status":"INSUFFICIENT_HISTORY","method":"linear health-index trend extrapolation","note":"At least 6 timeline points are required for the prototype trend estimate."}
    window=values[-min(20,len(values)):];x=np.arange(len(window),dtype=float);slope_per_step,intercept=np.polyfit(x,window,1);predicted=slope_per_step*x+intercept;ss_res=float(np.sum((window-predicted)**2));ss_tot=float(np.sum((window-np.mean(window))**2));r2=1.0-ss_res/ss_tot if ss_tot>1e-9 else 0.0;step_hours=max(float(step_minutes),1e-6)/60.0;slope_per_hour=slope_per_step/step_hours
    if slope_per_hour>=-0.15:return {"available":True,"rul_hours":None,"trend_per_hour":round(float(slope_per_hour),3),"confidence":round(max(0.0,min(1.0,r2)),2),"status":"STABLE_OR_NON_DEGRADING","method":"linear health-index trend extrapolation","note":"No finite RUL is extrapolated because the recent health trend is not degrading strongly enough."}
    current=float(window[-1]);hours_to_threshold=max(0.0,(current-critical_health_index)/(-slope_per_hour));horizon=min(hours_to_threshold,500.0);confidence=max(0.0,min(1.0,r2*min(1.0,len(window)/12.0)))
    return {"available":True,"rul_hours":round(float(horizon),2) if math.isfinite(horizon) else None,"trend_per_hour":round(float(slope_per_hour),3),"confidence":round(float(confidence),2),"status":"DEGRADING","critical_health_index":critical_health_index,"method":"linear health-index trend extrapolation","note":"Prototype RUL methodology only; not validated for a MALE-UAV piston engine without target-domain run-to-failure data."}

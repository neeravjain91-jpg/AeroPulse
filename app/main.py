from __future__ import annotations
import asyncio,json
import pandas as pd
from fastapi import FastAPI,HTTPException,WebSocket,WebSocketDisconnect
from fastapi.responses import FileResponse,HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from .config import DATA_SAMPLE_DIR,MODEL_DIR,PROJECT_NAME,PROJECT_VERSION,REQUIRED_MODEL_FILES,STATIC_DIR
from .inference import AeroTwinAI
from .mission_whatif import MissionScenario
from .mission_whatif_rul import MissionWhatIfRUL
from .replay import run_replay
from .risk import mission_risk
from .simulator import FAULTS,inject_fault,mission_adjust
from .vibration import VibrationAI,load_demo as load_vibration_demo
app=FastAPI(title=f"{PROJECT_NAME} / AeroTwin-MALE",version=PROJECT_VERSION,description="SIH26054 mission-aware Digital Twin demonstrator for UAV piston-engine health monitoring.");app.mount("/static",StaticFiles(directory=STATIC_DIR),name="static")
_ai=None;_ai_error=None;_demo=None;_vibration_ai=None;_vibration_demo=None
def _load_assets():
 global _ai,_ai_error,_demo,_vibration_ai,_vibration_demo
 try:_ai=AeroTwinAI();_ai_error=None
 except Exception as exc:_ai=None;_ai_error=str(exc)
 try:_vibration_ai=VibrationAI()
 except Exception:_vibration_ai=None
 _vibration_demo=load_vibration_demo();path=DATA_SAMPLE_DIR/"aces_demo.csv";_demo=pd.read_csv(path) if path.exists() else None
_load_assets()
class Scenario(BaseModel):
 fault:str="none";severity:float=Field(0.6,ge=0,le=1);altitude_ft:float=Field(8000,ge=0,le=60000);ambient_c:float=Field(35,ge=-60,le=80);duration_h:float=Field(6,gt=0,le=48);rapid_throttle:bool=False;operating_state:str="CRUISE"
class ReplayScenario(Scenario):
 steps:int=Field(48,ge=12,le=180);step_minutes:float=Field(5.0,ge=0.5,le=60);fault_onset_ratio:float=Field(0.35,ge=0,le=0.95)
class WhatIfRequest(BaseModel):
 baseline:Scenario
 alternative:Scenario
def _require_ai():
 if _ai is None:raise HTTPException(503,detail={"message":"Model assets are not ready. Train the models first.","command":'python scripts/train_models.py --data-dir "C:\\path\\to\\FINAL_DATASET"',"error":_ai_error})
 return _ai
def _require_demo():
 if _demo is None or _demo.empty:raise HTTPException(503,detail={"message":"Demo telemetry sample is missing.","command":'python scripts/train_models.py --data-dir "C:\\path\\to\\FINAL_DATASET"'})
 return _demo
def _clean_row(row):
 row=dict(row);row.pop("Robust_Anomaly_Score",None);row.pop("Health_State",None);return {k:(str(v) if k=="Operating_State" else float(v)) for k,v in row.items()}
def _base_sample(operating_state):
 candidates=_require_demo()
 if "Health_State" in candidates.columns:
  normal=candidates[candidates["Health_State"]=="Normal"]
  if not normal.empty:candidates=normal
 state_rows=candidates[candidates["Operating_State"].astype(str)==str(operating_state)]
 if not state_rows.empty:candidates=state_rows
 if "Robust_Anomaly_Score" in candidates.columns:candidates=candidates.sort_values("Robust_Anomaly_Score")
 row=candidates.iloc[0].to_dict();source=str(row.get("Health_State")) if "Health_State" in row else None;return _clean_row(row),source
def _mission_scenario(model:Scenario,name:str):
 return MissionScenario(name=name,altitude_ft=model.altitude_ft,ambient_c=model.ambient_c,duration_h=model.duration_h,rapid_throttle=model.rapid_throttle)
@app.get("/",response_class=HTMLResponse)
def home():
 html=(STATIC_DIR/"index.html").read_text(encoding="utf-8")
 return html.replace("</body>",'<script src="/static/dashboard_phase6.js"></script></body>')
@app.get("/api/status")
def status():
 return {"project":PROJECT_NAME,"version":PROJECT_VERSION,"models_ready":_ai is not None,"model_files":{n:(MODEL_DIR/n).exists() for n in REQUIRED_MODEL_FILES},"demo_ready":_demo is not None and not _demo.empty,"available_faults":sorted(FAULTS),"operating_states":_ai.twin.operating_states if _ai else [],"metrics_ready":(MODEL_DIR/"metrics.json").exists(),"vibration_model_ready":_vibration_ai is not None,"vibration_demo_ready":_vibration_demo is not None and not _vibration_demo.empty,"setup_error":_ai_error,"safety_note":"Research/SIH prototype; not certified for flight-safety or airworthiness decisions."}
@app.post("/api/reload")
def reload_assets():_load_assets();return status()
@app.get("/api/sample")
def sample(operating_state:str="CRUISE"):return _base_sample(operating_state)[0]
@app.post("/api/analyze")
def analyze(scenario:Scenario):
 ai=_require_ai()
 if scenario.fault not in FAULTS:raise HTTPException(400,detail=f"Unsupported fault: {scenario.fault}")
 base,source=_base_sample(scenario.operating_state);mission=mission_adjust(base,scenario.altitude_ft,scenario.ambient_c,scenario.duration_h,scenario.rapid_throttle);altered=inject_fault(mission,scenario.fault,scenario.severity);result=ai.analyze(altered,context=scenario.model_dump());risk=mission_risk(result,scenario.model_dump());result.update({"telemetry":altered,"source_reference_state":source,"scenario":scenario.model_dump(),"mission_risk":risk,"mission_risk_score":risk["score"],"mission_risk_level":risk["level"]});return result
@app.post("/api/mission-whatif-rul")
def mission_whatif_rul(request:WhatIfRequest):
 _require_ai();base,source=_base_sample(request.baseline.operating_state);engine=MissionWhatIfRUL({"injector":0.05,"lubrication":0.04,"thermal":0.03,"mechanical":0.02,"electrical":0.01,"sensor":0.02});result=engine.compare(base,_mission_scenario(request.baseline,"baseline"),_mission_scenario(request.alternative,"alternative"));result["source_reference_state"]=source;return result
@app.post("/api/replay")
def replay(scenario:ReplayScenario):
 ai=_require_ai();base,source=_base_sample(scenario.operating_state);payload=scenario.model_dump();result=run_replay(ai,base,payload,scenario.steps,scenario.step_minutes,scenario.fault_onset_ratio);result["scenario"]=payload;result["source_reference_state"]=source;result["disclaimer"]="Mission replay, early-warning and RUL outputs are prototype method demonstrations, not operational airworthiness determinations.";return result
@app.get("/api/metrics")
def metrics():
 path=MODEL_DIR/"metrics.json"
 if not path.exists():raise HTTPException(404,detail="Train models first; metrics.json is missing.")
 return json.loads(path.read_text())
@app.get("/api/model-manifest")
def model_manifest():
 path=MODEL_DIR/"model_manifest.json"
 if not path.exists():raise HTTPException(404,detail="Model manifest is not available; retrain with the current training script.")
 return json.loads(path.read_text())
@app.get("/api/vibration/demo")
def vibration_demo(condition:str="Normal"):
 if _vibration_ai is None or _vibration_demo is None or _vibration_demo.empty:raise HTTPException(503,detail="CWRU vibration model/demo is not available. Retrain models first.")
 candidates=_vibration_demo
 if "Fault" in candidates.columns:
  matched=candidates[candidates["Fault"].astype(str).str.lower()==str(condition).lower()]
  if not matched.empty:candidates=matched
 row=candidates.iloc[0].to_dict();features={f:float(row[f]) for f in _vibration_ai.features};result=_vibration_ai.analyze(features);result["input_features"]=features;result["source_label"]=str(row.get("Fault","unknown"));return result
@app.websocket("/ws/telemetry")
async def telemetry_stream(websocket:WebSocket):
 await websocket.accept()
 try:
  config=await websocket.receive_json();interval=max(0.05,min(float(config.pop("playback_interval_s",0.25)),2.0));scenario=ReplayScenario(**config);ai=_require_ai();base,source=_base_sample(scenario.operating_state);payload=scenario.model_dump();result=run_replay(ai,base,payload,scenario.steps,scenario.step_minutes,scenario.fault_onset_ratio);await websocket.send_json({"type":"start","scenario":payload,"source_reference_state":source})
  for point in result["timeline"]:await websocket.send_json({"type":"telemetry","data":point});await asyncio.sleep(interval)
  await websocket.send_json({"type":"summary","data":result["summary"]});await websocket.close()
 except WebSocketDisconnect:return
 except Exception as exc:
  try:await websocket.send_json({"type":"error","message":str(exc)});await websocket.close()
  except Exception:pass

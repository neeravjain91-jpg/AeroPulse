import json

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT, STATIC_DIR
from .inference import AeroTwinAI
from .simulator import inject_fault, mission_adjust

app = FastAPI(title="AeroPulse-X / AeroTwin-MALE", version="0.1.0")
ai = AeroTwinAI()
demo = pd.read_csv(ROOT / "data_sample/aces_demo.csv")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class Scenario(BaseModel):
    fault: str = "none"
    severity: float = Field(0.6, ge=0, le=1)
    altitude_ft: float = 3000
    ambient_c: float = 25
    duration_h: float = 4
    rapid_throttle: bool = False


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/sample")
def sample():
    row = demo.sample(1).iloc[0].to_dict()
    row.pop("Robust_Anomaly_Score", None)
    row.pop("Health_State", None)
    return row


@app.post("/api/analyze")
def analyze(scenario: Scenario):
    row = demo.sample(1).iloc[0].to_dict()
    source_reference_state = row.get("Health_State")
    row.pop("Robust_Anomaly_Score", None)
    row.pop("Health_State", None)

    base = {
        key: (str(value) if key == "Operating_State" else float(value))
        for key, value in row.items()
    }

    mission = mission_adjust(
        base,
        scenario.altitude_ft,
        scenario.ambient_c,
        scenario.duration_h,
        scenario.rapid_throttle,
    )
    altered = inject_fault(mission, scenario.fault, scenario.severity)
    result = ai.analyze(altered)

    risk = min(
        99,
        max(
            1,
            int(
                (100 - result["health_index"]) * 0.9
                + max(0, scenario.duration_h - 4) * 2
                + max(0, scenario.ambient_c - 35) * 0.7
                + max(0, scenario.altitude_ft - 8000) / 1000 * 2
            ),
        ),
    )

    result.update(
        {
            "telemetry": altered,
            "source_reference_state": source_reference_state,
            "scenario": scenario.model_dump(),
            "mission_risk_score": risk,
            "mission_risk_level": "HIGH" if risk >= 70 else "MEDIUM" if risk >= 40 else "LOW",
        }
    )
    return result


@app.get("/api/metrics")
def metrics():
    return json.loads((ROOT / "models/metrics.json").read_text())

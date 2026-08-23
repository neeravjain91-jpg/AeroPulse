from __future__ import annotations

import asyncio
import json

import pandas as pd
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import (
    DATA_SAMPLE_DIR,
    MODEL_DIR,
    PROJECT_NAME,
    PROJECT_VERSION,
    REQUIRED_MODEL_FILES,
    STATIC_DIR,
)
from .engine_model import ReducedOrderPistonEngine
from .inference import AeroTwinAI
from .mission_whatif import MissionScenario
from .mission_whatif_rul import MissionWhatIfRUL
from .replay import run_replay
from .risk import mission_risk
from .simulator import FAULTS, inject_fault, mission_adjust
from .telemetry import telemetry_from_engine
from .uav_mission import UAVMissionSimulator
from .vibration import VibrationAI, load_demo as load_vibration_demo


app = FastAPI(
    title=f"{PROJECT_NAME} / AeroTwin-MALE",
    version=PROJECT_VERSION,
    description=(
        "SIH26054 mission-aware Digital Twin demonstrator "
        "for UAV piston-engine health monitoring."
    ),
)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


_ai: AeroTwinAI | None = None
_ai_error: str | None = None
_demo: pd.DataFrame | None = None
_vibration_ai: VibrationAI | None = None
_vibration_demo: pd.DataFrame | None = None

_ENGINE = ReducedOrderPistonEngine()


def _load_assets() -> None:
    global _ai
    global _ai_error
    global _demo
    global _vibration_ai
    global _vibration_demo

    health_model_file = MODEL_DIR / "aces_health.joblib"
    anomaly_model_file = MODEL_DIR / "aces_anomaly.joblib"
    healthy_ref_file = MODEL_DIR / "healthy_reference.json"
    demo_file = DATA_SAMPLE_DIR / "aces_demo.csv"

    if not (health_model_file.exists() and anomaly_model_file.exists() and healthy_ref_file.exists() and demo_file.exists()):
        try:
            from scripts.train_models import train_all
            train_all()
        except Exception as e:
            print(f"Auto-train note: {e}")

    try:
        _ai = AeroTwinAI()
        _ai_error = None
    except Exception as exc:
        _ai = None
        _ai_error = str(exc)

    try:
        _vibration_ai = VibrationAI()
    except Exception:
        _vibration_ai = None

    _vibration_demo = load_vibration_demo()

    path = DATA_SAMPLE_DIR / "aces_demo.csv"

    if path.exists():
        _demo = pd.read_csv(path)
    else:
        _demo = None


_load_assets()


class Scenario(BaseModel):
    fault: str = "none"
    severity: float = Field(0.6, ge=0, le=1)
    altitude_ft: float = Field(8000, ge=0, le=60000)
    ambient_c: float = Field(35, ge=-60, le=80)
    duration_h: float = Field(6, gt=0, le=48)
    rapid_throttle: bool = False
    operating_state: str = "CRUISE"


class ReplayScenario(Scenario):
    steps: int = Field(48, ge=12, le=180)
    step_minutes: float = Field(5.0, ge=0.5, le=60)
    fault_onset_ratio: float = Field(0.35, ge=0, le=0.95)


class WhatIfRequest(BaseModel):
    baseline: Scenario
    alternative: Scenario


class LiveMissionConfig(Scenario):
    steps: int = Field(120, ge=12, le=360)
    playback_interval_s: float = Field(0.25, ge=0.05, le=2.0)
    fault_onset_ratio: float = Field(0.35, ge=0, le=0.95)

    max_altitude_ft: float = Field(
        20000,
        ge=3000,
        le=60000,
    )

    cruise_altitude_ft: float = Field(
        8000,
        ge=1000,
        le=60000,
    )

    hot_weather: bool = False
    mission_mode: str = "standard"


def _require_ai() -> AeroTwinAI:
    if _ai is None:
        raise HTTPException(
            503,
            detail={
                "message": (
                    "Model assets are not ready. "
                    "Train the models first."
                ),
                "command": (
                    'python scripts/train_models.py '
                    '--data-dir "C:\\path\\to\\FINAL_DATASET"'
                ),
                "error": _ai_error,
            },
        )

    return _ai


def _require_demo() -> pd.DataFrame:
    if _demo is None or _demo.empty:
        raise HTTPException(
            503,
            detail={
                "message": (
                    "Demo telemetry sample is missing."
                ),
                "command": (
                    'python scripts/train_models.py '
                    '--data-dir "C:\\path\\to\\FINAL_DATASET"'
                ),
            },
        )

    return _demo


def _clean_row(row: dict) -> dict:
    row = dict(row)

    row.pop("Robust_Anomaly_Score", None)
    row.pop("Health_State", None)

    return {
        key: (
            str(value)
            if key == "Operating_State"
            else float(value)
        )
        for key, value in row.items()
    }


def _base_sample(
    operating_state: str,
) -> tuple[dict, str | None]:

    candidates = _require_demo()

    if "Health_State" in candidates.columns:
        normal = candidates[
            candidates["Health_State"] == "Normal"
        ]

        if not normal.empty:
            candidates = normal

    state_rows = candidates[
        candidates["Operating_State"].astype(str)
        == str(operating_state)
    ]

    if not state_rows.empty:
        candidates = state_rows

    if "Robust_Anomaly_Score" in candidates.columns:
        candidates = candidates.sort_values(
            "Robust_Anomaly_Score"
        )

    row = candidates.iloc[0].to_dict()

    source = (
        str(row.get("Health_State"))
        if "Health_State" in row
        else None
    )

    return _clean_row(row), source


def _mission_scenario(
    model: Scenario,
    name: str,
):
    return MissionScenario(
        name=name,
        altitude_ft=model.altitude_ft,
        ambient_c=model.ambient_c,
        duration_h=model.duration_h,
        rapid_throttle=model.rapid_throttle,
    )


def _round_telemetry(data: dict) -> dict:
    result = {}

    for key, value in data.items():

        if isinstance(value, bool):
            result[key] = value

        elif isinstance(value, (int, float)):
            result[key] = round(
                float(value),
                4,
            )

        else:
            result[key] = value

    return result


def _build_live_engine_data(
    mission_point,
) -> dict:
    """
    Generate engine telemetry from the reduced-order
    piston-engine model.

    This is the simulation equivalent of an engine ECU
    producing sensor values.
    """

    throttle = max(
        0.0,
        min(
            1.0,
            float(
                mission_point.throttle
            ),
        ),
    )

    load = max(
        0.05,
        min(
            1.15,
            float(
                mission_point.load
            ),
        ),
    )

    rpm = 3000.0 * (
        0.92 + 0.12 * throttle
    )

    return _ENGINE.simulate(
        rpm=rpm,
        throttle=throttle,
        altitude_ft=float(
            mission_point.altitude_ft
        ),
        ambient_c=float(
            mission_point.ambient_c
        ),
        load=load,
    )


def _apply_live_fault(
    telemetry: dict,
    config: LiveMissionConfig,
    step: int,
) -> tuple[dict, float]:

    fault = str(
        config.fault
    ).lower()

    if fault == "none":
        return telemetry, 0.0

    total_steps = int(
        config.steps
    )

    onset_step = int(
        total_steps
        * float(
            config.fault_onset_ratio
        )
    )

    if step < onset_step:
        return telemetry, 0.0

    progress = (
        (
            step
            - onset_step
            + 1
        )
        / max(
            1,
            total_steps
            - onset_step,
        )
    )

    progress = max(
        0.0,
        min(
            1.0,
            progress,
        ),
    )

    effective_severity = (
        float(config.severity)
        * progress
    )

    altered = inject_fault(
        telemetry,
        fault,
        effective_severity,
    )

    altered[
        "Degradation_Severity"
    ] = effective_severity

    return altered, effective_severity


@app.get(
    "/",
    response_class=HTMLResponse,
)
def home():
    return (
        STATIC_DIR / "index.html"
    ).read_text(
        encoding="utf-8"
    )


@app.get("/api/status")
def status():

    return {
        "project": PROJECT_NAME,
        "version": PROJECT_VERSION,
        "models_ready": _ai is not None,
        "model_files": {
            name: (
                MODEL_DIR / name
            ).exists()
            for name in REQUIRED_MODEL_FILES
        },
        "demo_ready": (
            _demo is not None
            and not _demo.empty
        ),
        "available_faults": sorted(
            FAULTS
        ),
        "operating_states": (
            _ai.twin.operating_states
            if _ai
            else []
        ),
        "metrics_ready": (
            MODEL_DIR / "metrics.json"
        ).exists(),
        "vibration_model_ready": (
            _vibration_ai is not None
        ),
        "vibration_demo_ready": (
            _vibration_demo is not None
            and not _vibration_demo.empty
        ),
        "setup_error": _ai_error,
        "telemetry_interface": {
            "version": "1.0",
            "schema": "UAVTelemetry",
            "source": "uav_simulator",
            "hardware_ready_interface": True,
        },
        "capabilities": [
            "healthy-reference Digital Twin",
            "four-state AI health monitoring",
            "unsupervised anomaly detection",
            "sensor-trust assessment",
            "fault evidence and maintenance advisory",
            "mission-condition simulation",
            "UAV mission simulation",
            "hardware-equivalent telemetry schema",
            "simulated real-time telemetry",
            "live WebSocket telemetry",
            "mission replay / early-warning comparison",
            "prototype degradation and RUL methodology",
        ],
        "safety_note": (
            "Research/SIH prototype; not certified "
            "for flight-safety or airworthiness decisions."
        ),
    }


@app.post("/api/reload")
def reload_assets():
    _load_assets()
    return status()


@app.get("/api/sample")
def sample(
    operating_state: str = "CRUISE",
):
    return _base_sample(
        operating_state
    )[0]


@app.post("/api/analyze")
def analyze(
    scenario: Scenario,
):

    ai = _require_ai()

    if scenario.fault not in FAULTS:
        raise HTTPException(
            400,
            detail=(
                f"Unsupported fault: "
                f"{scenario.fault}"
            ),
        )

    base, source = _base_sample(
        scenario.operating_state
    )

    mission = mission_adjust(
        base,
        scenario.altitude_ft,
        scenario.ambient_c,
        scenario.duration_h,
        scenario.rapid_throttle,
    )

    altered = inject_fault(
        mission,
        scenario.fault,
        scenario.severity,
    )

    context = scenario.model_dump()

    result = ai.analyze(
        altered,
        context=context,
    )

    risk = mission_risk(
        result,
        context,
    )

    result.update(
        {
            "telemetry": altered,
            "source_reference_state": source,
            "scenario": context,
            "mission_risk": risk,
            "mission_risk_score": risk["score"],
            "mission_risk_level": risk["level"],
        }
    )

    return result


@app.post("/api/mission-whatif-rul")
def mission_whatif_rul(
    request: WhatIfRequest,
):

    _require_ai()

    base, source = _base_sample(
        request.baseline.operating_state
    )

    engine = MissionWhatIfRUL(
        {
            "injector": 0.05,
            "lubrication": 0.04,
            "thermal": 0.03,
            "mechanical": 0.02,
            "electrical": 0.01,
            "sensor": 0.02,
        }
    )

    result = engine.compare(
        base,
        _mission_scenario(
            request.baseline,
            "baseline",
        ),
        _mission_scenario(
            request.alternative,
            "alternative",
        ),
    )

    result[
        "source_reference_state"
    ] = source

    return result


@app.post("/api/replay")
def replay(
    scenario: ReplayScenario,
):

    ai = _require_ai()

    base, source = _base_sample(
        scenario.operating_state
    )

    payload = scenario.model_dump()

    result = run_replay(
        ai,
        base,
        payload,
        scenario.steps,
        scenario.step_minutes,
        scenario.fault_onset_ratio,
    )

    result["scenario"] = payload

    result[
        "source_reference_state"
    ] = source

    result["disclaimer"] = (
        "Mission replay, early-warning and RUL "
        "outputs are prototype method demonstrations, "
        "not operational airworthiness determinations."
    )

    return result


@app.get("/api/metrics")
def metrics():

    path = MODEL_DIR / "metrics.json"

    if not path.exists():
        raise HTTPException(
            404,
            detail=(
                "Train models first; "
                "metrics.json is missing."
            ),
        )

    return json.loads(
        path.read_text()
    )


@app.get("/api/model-manifest")
def model_manifest():

    path = MODEL_DIR / "model_manifest.json"

    if not path.exists():
        raise HTTPException(
            404,
            detail=(
                "Model manifest is not available; "
                "retrain with the current training script."
            ),
        )

    return json.loads(
        path.read_text()
    )


@app.get("/api/vibration/demo")
def vibration_demo(
    condition: str = "Normal",
):

    if (
        _vibration_ai is None
        or _vibration_demo is None
        or _vibration_demo.empty
    ):
        raise HTTPException(
            503,
            detail=(
                "CWRU vibration model/demo is not "
                "available. Retrain models first."
            ),
        )

    candidates = _vibration_demo

    if "Fault" in candidates.columns:

        matched = candidates[
            candidates["Fault"]
            .astype(str)
            .str.lower()
            == str(condition).lower()
        ]

        if not matched.empty:
            candidates = matched

    row = candidates.iloc[0].to_dict()

    features = {
        feature: float(row[feature])
        for feature in _vibration_ai.features
    }

    result = _vibration_ai.analyze(
        features
    )

    result["input_features"] = features

    result["source_label"] = str(
        row.get(
            "Fault",
            "unknown",
        )
    )

    return result


@app.websocket("/ws/telemetry")
async def telemetry_stream(
    websocket: WebSocket,
):
    """
    Live simulated UAV telemetry pipeline.

    UAV mission
        ↓
    Engine simulation
        ↓
    UAVTelemetry hardware-equivalent packet
        ↓
    Fault injection
        ↓
    Digital Twin
        ↓
    AI/ML
        ↓
    Risk / advisory
        ↓
    WebSocket
        ↓
    GCS dashboard
    """

    await websocket.accept()

    try:

        config = await websocket.receive_json()

        playback_interval = max(
            0.05,
            min(
                float(
                    config.pop(
                        "playback_interval_s",
                        0.25,
                    )
                ),
                2.0,
            ),
        )

        live_config = LiveMissionConfig(
            **config
        )

        if live_config.fault not in FAULTS:

            await websocket.send_json(
                {
                    "type": "error",
                    "message": (
                        f"Unsupported fault: "
                        f"{live_config.fault}"
                    ),
                }
            )

            await websocket.close()

            return

        ai = _require_ai()

        mission = UAVMissionSimulator(
            duration_min=(
                float(
                    live_config.duration_h
                )
                * 60.0
            ),
            max_altitude_ft=(
                float(
                    live_config.max_altitude_ft
                )
            ),
            cruise_altitude_ft=(
                float(
                    live_config.cruise_altitude_ft
                )
            ),
            ambient_c=(
                float(
                    live_config.ambient_c
                )
            ),
            hot_weather=(
                bool(
                    live_config.hot_weather
                )
            ),
            rapid_throttle=(
                bool(
                    live_config.rapid_throttle
                )
            ),
        )

        total_steps = int(
            live_config.steps
        )

        await websocket.send_json(
            {
                "type": "start",
                "mode": "live_uav_mission",
                "telemetry_schema": "UAVTelemetry",
                "telemetry_version": "1.0",
                "source": "uav_simulator",
                "scenario": (
                    live_config.model_dump()
                ),
                "mission": {
                    "duration_min": (
                        mission.duration_min
                    ),
                    "max_altitude_ft": (
                        mission.max_altitude_ft
                    ),
                    "cruise_altitude_ft": (
                        mission.cruise_altitude_ft
                    ),
                    "hot_weather": (
                        mission.hot_weather
                    ),
                    "rapid_throttle": (
                        mission.rapid_throttle
                    ),
                },
            }
        )

        health_history: list[float] = []

        peak_risk = 0.0
        final_analysis = None
        final_risk = None

        for step in range(
            total_steps
        ):

            mission_point = mission.point(
                step,
                total_steps,
            )

            engine_data = (
                _build_live_engine_data(
                    mission_point
                )
            )

            telemetry_packet = (
                telemetry_from_engine(
                    engine_data,
                    mission_point,
                    source="uav_simulator",
                )
            )

            telemetry = (
                telemetry_packet.to_dict()
            )

            altered, fault_severity = (
                _apply_live_fault(
                    telemetry,
                    live_config,
                    step,
                )
            )

            altered[
                "Degradation_Severity"
            ] = fault_severity

            context = {
                **live_config.model_dump(),

                "data_source": (
                    "uav_simulation"
                ),

                "rpm": (
                    telemetry_packet.Engine_RPM
                ),

                "throttle": (
                    telemetry_packet.Throttle
                ),

                "load": (
                    telemetry_packet.Load
                ),

                "mission_phase": (
                    telemetry_packet.Mission_Phase
                ),

                "mission_time_min": (
                    telemetry_packet.Mission_Time_Min
                ),

                "mission_step": (
                    telemetry_packet.Mission_Step
                ),

                "altitude_ft": (
                    telemetry_packet.Altitude_ft
                ),

                "ambient_c": (
                    telemetry_packet.Ambient_C
                ),
            }

            analysis = ai.analyze(
                altered,
                context=context,
            )

            risk = mission_risk(
                analysis,
                context,
            )

            health_history.append(
                float(
                    analysis[
                        "health_index"
                    ]
                )
            )

            peak_risk = max(
                peak_risk,
                float(
                    risk["score"]
                ),
            )

            final_analysis = analysis
            final_risk = risk

            if analysis[
                "fault_candidates"
            ]:

                primary_fault = (
                    analysis[
                        "fault_candidates"
                    ][0]["name"]
                )

            else:

                primary_fault = "None"

            point = {
                "step": step,

                "time_min": round(
                    telemetry_packet.Mission_Time_Min,
                    3,
                ),

                "mission_phase": (
                    telemetry_packet.Mission_Phase
                ),

                "altitude_ft": round(
                    telemetry_packet.Altitude_ft,
                    2,
                ),

                "ambient_c": round(
                    telemetry_packet.Ambient_C,
                    2,
                ),

                "throttle": round(
                    telemetry_packet.Throttle,
                    4,
                ),

                "load": round(
                    telemetry_packet.Load,
                    4,
                ),

                "operating_state": (
                    telemetry_packet.Operating_State
                ),

                "rapid_throttle": (
                    telemetry_packet.Rapid_Throttle
                ),

                "health_state": (
                    analysis[
                        "health_state"
                    ]
                ),

                "ml_health_state": (
                    analysis[
                        "ml_health_state"
                    ]
                ),

                "health_index": (
                    analysis[
                        "health_index"
                    ]
                ),

                "health_confidence": (
                    analysis[
                        "health_confidence"
                    ]
                ),

                "anomaly_score": (
                    analysis[
                        "anomaly_score"
                    ]
                ),

                "anomaly_flag": (
                    analysis[
                        "anomaly_flag"
                    ]
                ),

                "residual_rms": round(
                    float(
                        analysis[
                            "twin"
                        ][
                            "residual_rms"
                        ]
                    ),
                    3,
                ),

                "max_abs_z": round(
                    float(
                        analysis[
                            "twin"
                        ][
                            "max_abs_z"
                        ]
                    ),
                    3,
                ),

                "risk_score": (
                    risk["score"]
                ),

                "risk_level": (
                    risk["level"]
                ),

                "primary_fault": (
                    primary_fault
                ),

                "sensor_trust": (
                    analysis[
                        "sensor_health"
                    ][
                        "overall_trust_score"
                    ]
                ),

                "fault_severity": round(
                    fault_severity,
                    4,
                ),

                "telemetry_version": (
                    telemetry_packet.telemetry_version
                ),

                "telemetry_source": (
                    telemetry_packet.source
                ),

                "telemetry": (
                    _round_telemetry(
                        altered
                    )
                ),
            }

            await websocket.send_json(
                {
                    "type": "telemetry",
                    "data": point,
                }
            )

            await asyncio.sleep(
                playback_interval
            )

        final_point = mission.point(
            total_steps - 1,
            total_steps,
        )

        summary = {
            "steps": total_steps,

            "duration_min": round(
                mission.duration_min,
                2,
            ),

            "final_health_index": (
                final_analysis[
                    "health_index"
                ]
                if final_analysis
                else None
            ),

            "final_health_state": (
                final_analysis[
                    "health_state"
                ]
                if final_analysis
                else None
            ),

            "peak_risk_score": round(
                peak_risk,
                2,
            ),

            "final_risk_level": (
                final_risk["level"]
                if final_risk
                else None
            ),

            "final_mission_phase": (
                final_point.mission_phase
            ),

            "fault": (
                live_config.fault
            ),

            "fault_severity": (
                live_config.severity
            ),

            "fault_onset_ratio": (
                live_config.fault_onset_ratio
            ),

            "health_history_points": len(
                health_history
            ),

            "telemetry_schema": (
                "UAVTelemetry"
            ),

            "telemetry_version": (
                "1.0"
            ),

            "source": (
                "uav_simulator"
            ),

            "mode": (
                "live_uav_mission"
            ),

            "note": (
                "Simulated UAV mission telemetry "
                "feeding the AeroPulse Digital Twin "
                "and AI monitoring pipeline. "
                "Prototype only."
            ),
        }

        await websocket.send_json(
            {
                "type": "summary",
                "data": summary,
            }
        )

        await websocket.close()

    except WebSocketDisconnect:
        return

    except Exception as exc:

        try:

            await websocket.send_json(
                {
                    "type": "error",
                    "message": str(exc),
                }
            )

            await websocket.close()

        except Exception:
            pass
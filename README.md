# AeroPulse-X — AeroTwin-MALE

Research-grade SIH26054 prototype for an AI-enabled, mission-aware Digital Twin for MALE-UAV aero-piston engine health monitoring.

## Core flow

```text
Telemetry / simulator
        ↓
Healthy-reference Digital Twin
        ↓
Expected ↔ Observed residuals
        ↓
AI health + anomaly models
        ↓
Fault evidence / sensor checks
        ↓
Mission-condition simulation
        ↓
Risk + maintenance advisory
        ↓
GCS-style dashboard
```

## Current prototype
- ACES-based four-state engine health model: Normal / Watch / Warning / Critical
- Leakage-safe feature set (`Robust_Anomaly_Score` is excluded from model inputs)
- Healthy-reference Digital Twin by operating state
- Residual and z-score comparison between expected and observed telemetry
- Unsupervised anomaly detection trained on healthy ACES telemetry
- Controlled fault injection: overheating, lubrication degradation, misfire-like behaviour, injector abnormality and sensor drift
- Mission simulation: altitude, ambient temperature, endurance duration and rapid throttle
- Prototype maintenance advisory layer
- CWRU vibration/bearing supporting model
- Marine-engine fault experiment retained as supporting research, not claimed as validated MALE-UAV diagnosis

## Repository policy
Raw datasets, trained `.joblib` artifacts, virtual environments, caches and `node_modules` are intentionally not tracked. Train the models locally from your dataset.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/train_models.py --data-dir "C:\path\to\FINAL_DATASET"
python run.py
```

Open **http://127.0.0.1:8000/**.

## Scientific limitations
This is an SIH proof-of-concept, not a certified flight-safety system. Mission-risk rules and simplified environmental response functions must be replaced by validated aero-piston-engine maps/physics for operational use. Marine and CWRU data are supporting domains and must not be presented as MALE-UAV validation.

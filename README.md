# AeroPulse-X — Mission-Aware Digital Twin for MALE-UAV Engine Health

**SIH26054 research prototype** for an AI-enabled Digital Twin of a MALE-UAV aero-piston engine.

## Core flow

```text
Telemetry / mission simulator
        ↓
Context-aware healthy-reference Digital Twin
        ↓
Expected ↔ Observed residuals
        ↓
AI health classification + anomaly detection
        ↓
Sensor-trust assessment + fault evidence
        ↓
Mission-risk analysis + maintenance advisory
        ↓
Mission replay + degradation/RUL methodology demonstrator
        ↓
GCS-style dashboard
```

## Current build

- ACES UAV data as the primary engine-health source
- Normal / Watch / Warning / Critical health monitoring
- leakage-safe inputs: Robust_Anomaly_Score and derived robust-z fields are excluded
- held-out-flight validation when full ACES health data are available
- context-aware Digital Twin for altitude, temperature, endurance and rapid throttle
- Isolation Forest trained only on healthy ACES samples
- controlled overheating, lubrication, misfire-like, injector, sensor-drift and electrical faults
- sensor-trust logic and explainable maintenance advisory
- explainable mission-risk / mission-reliability index
- mission replay with fault onset and warning timing
- prototype degradation/RUL trend method
- separate CWRU vibration module
- Marine fault experiment retained as research-only
- FastAPI REST + WebSocket backend and GCS dashboard

## Quick start — Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts/train_models.py --data-dir "C:\path\to\FINAL_DATASET"
python run.py
```

Open **http://127.0.0.1:8000/**. FastAPI docs are at **http://127.0.0.1:8000/docs**.

`0.0.0.0:8000` is the bind address; do not type it into the browser.

## Model validation

The richer ACES training path uses raw measurements including RPM, EGT1/2/3, CHT, fuel flow, oil temperature/pressure, battery voltage/current, alternator temperature, EFI temperatures, MAP injector and operating state. Test evaluation is grouped by held-out **Flight** IDs to reduce leakage from neighbouring telemetry rows.

The reference build on the supplied dataset produced approximately **87.2% ACES health accuracy** and **80.4% balanced accuracy**. Use your locally generated `models/metrics.json` as the authoritative result for each run.

## RUL

The supplied datasets do not provide clean MALE-UAV aero-piston run-to-failure trajectories, so AeroPulse-X does not claim operational RUL accuracy. Mission Replay provides a clearly labelled trend-extrapolation method demonstrator. `scripts/train_rul_cmapss.py` optionally validates an RUL workflow on NASA C-MAPSS-style turbofan benchmark files; that is methodology validation only, not piston-engine validation.

## API

- `GET /api/status`
- `POST /api/analyze`
- `POST /api/replay`
- `GET /api/metrics`
- `GET /api/model-manifest`
- `GET /api/vibration/demo`
- `POST /api/reload`
- `WS /ws/telemetry`

## Safety / scientific scope

This is an **SIH/research demonstrator**, not a certified flight-safety, airworthiness, maintenance-release or operational defence system. Mission-risk, sensor-trust and RUL outputs require validation using the target aero-piston engine, approved performance maps, calibrated sensors and degradation evidence before operational use.

> **Pitch:** AeroPulse-X continuously mirrors expected engine behaviour, compares it with observed telemetry, detects and explains emerging anomalies, evaluates sensor trust, projects degradation, replays mission behaviour, and translates engine condition into mission-level maintenance decision support.

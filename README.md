# AeroPulse-X — Mission-Aware Digital Twin for MALE-UAV Engine Health

**SIH26054 research prototype** for an AI-enabled, real-time Digital Twin of a MALE-UAV aero-piston engine.

AeroPulse-X turns engine telemetry into a decision-support pipeline:

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

## What the current build does

- Four-state engine health monitoring: **Normal / Watch / Warning / Critical**
- Primary model trained from **NASA ACES UAV engine/mechanical data**
- Leakage-safe training: `Robust_Anomaly_Score` and derived robust-z fields are excluded from health-model inputs
- **Held-out-flight validation** when the full ACES dataset is available
- Context-aware Digital Twin reference for altitude, temperature, endurance and rapid-throttle scenarios
- Isolation Forest anomaly detection trained only on healthy ACES samples
- Controlled fault injection:
  - overheating
  - lubrication degradation
  - misfire-like behaviour
  - injector abnormality
  - sensor drift
  - battery / alternator abnormality
- Sensor-trust logic that can distinguish some isolated sensor inconsistencies from corroborated engine behaviour
- Explainable mission-risk breakdown
- Mission replay with fault onset, first AI warning and reference-alarm timing
- Prototype degradation trend and RUL methodology demonstrator
- Supporting **CWRU vibration/bearing model** kept separate from the main UAV-health model
- Supporting **Marine Engine fault-signature experiment** kept research-only because cross-load generalization is weak
- FastAPI backend + offline-friendly GCS-style dashboard

## Why the datasets are not merged blindly

The supplied data originate from different platforms and sensing domains. AeroPulse-X therefore uses **model-level fusion**, not row-level concatenation:

```text
ACES UAV data ─────────────→ primary engine-health / Digital Twin model
CWRU bearing data ─────────→ supporting vibration-condition model
Marine engine fault data ──→ supporting fault-signature research only
```

That preserves scientific validity and avoids presenting cross-domain data as MALE-UAV ground truth.

## Quick start — Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

python scripts/train_models.py --data-dir "C:\path\to\FINAL_DATASET"
python run.py
```

Open:

```text
http://127.0.0.1:8000/
```

FastAPI documentation:

```text
http://127.0.0.1:8000/docs
```

> `0.0.0.0:8000` is the server bind address. Use `127.0.0.1:8000` or `localhost:8000` in the browser.

## Reproducible model environment

`scikit-learn==1.8.0` is pinned because persisted scikit-learn models should be loaded with the same library version used to create them. The repository intentionally does **not** track `.joblib` artifacts; train them locally from your dataset.

## Model training

The preferred training path uses:

```text
FINAL_DATASET/ACES/aces_health.csv
```

When that file is present, the script uses the richer raw ACES measurements including:

- Engine RPM
- EGT1 / EGT2 / EGT3
- CHT
- Fuel flow
- Oil temperature / pressure
- Battery voltage / current
- Alternator temperature
- EFI fuel temperature
- EFI water temperature
- MAP injector
- Operating state

The split is performed by **held-out flight groups**, which is stronger than randomly mixing neighbouring telemetry rows across train and test.

The current reference build on the supplied dataset produced approximately:

- ACES health accuracy: **87.2%**
- ACES balanced accuracy: **80.4%**

Always use the locally generated `models/metrics.json` as the authoritative result for your current training run.

## RUL strategy

The supplied datasets do not provide clean MALE-UAV aero-piston run-to-failure trajectories. AeroPulse-X therefore does **not** claim operational RUL accuracy.

Two layers are provided:

1. Runtime **trend-extrapolation RUL method demonstrator** from a mission replay.
2. Optional `scripts/train_rul_cmapss.py` for validating an RUL modelling methodology on NASA C-MAPSS-style turbofan benchmark data.

C-MAPSS validation must be presented as **method validation only**, not target-engine validation.

## API

- `GET /api/status` — model/data readiness and capabilities
- `POST /api/analyze` — one mission-condition/fault snapshot
- `POST /api/replay` — mission timeline, fault onset, warning timing and RUL method demonstration
- `GET /api/metrics` — generated validation metrics
- `GET /api/model-manifest` — feature/split/data-role manifest
- `GET /api/vibration/demo` — supporting CWRU vibration classifier demo
- `POST /api/reload` — reload trained assets without changing code

## Repository structure

```text
AeroPulse-X/
├── app/
│   ├── main.py              # FastAPI routes and asset lifecycle
│   ├── inference.py         # AI health/anomaly inference
│   ├── digital_twin.py      # context-aware healthy reference twin
│   ├── simulator.py         # mission adjustments + fault injection
│   ├── sensor_health.py     # cross-sensor trust logic
│   ├── risk.py              # explainable mission-risk index
│   ├── degradation.py       # RUL/trend method demonstrator
│   ├── replay.py            # mission replay engine
│   ├── advisory.py          # fault evidence + maintenance advice
│   └── vibration.py         # isolated CWRU supporting model
├── scripts/
│   ├── train_models.py
│   └── train_rul_cmapss.py
├── static/index.html        # offline-friendly GCS dashboard
├── tests/
├── docs/
├── requirements.txt
└── run.py
```

## Safety and scientific scope

This project is an **SIH / research software demonstrator**. It is not a certified flight-safety, airworthiness, maintenance-release or operational defence system. Mission-risk, sensor-trust and RUL outputs require validation using the target aero-piston engine, its approved performance maps, calibrated sensor data and run-to-failure/degradation evidence before operational use.

## SIH pitch

> **AeroPulse-X continuously mirrors expected engine behaviour, compares it with observed telemetry, detects and explains emerging anomalies, evaluates sensor trust, projects degradation, replays mission behaviour, and translates engine condition into mission-level maintenance decision support.**

See `docs/SIH_DEMO.md` for the recommended live demonstration sequence.

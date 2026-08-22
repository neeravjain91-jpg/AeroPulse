# Architecture

```text
Telemetry / Simulator
        ↓
Validation + preprocessing
        ↓
Healthy-reference Digital Twin
        ↓
Expected ↔ Observed → residuals
        ↓
AI health model + anomaly model
        ↓
Fault evidence / sensor checks
        ↓
Health / degradation layer
        ↓
Mission scenario engine
        ↓
Risk + maintenance advisory
        ↓
GCS dashboard / replay
```

## Innovation focus
1. Hybrid reference-twin + data-driven residual intelligence.
2. Mission-aware health interpretation rather than threshold alerting only.
3. Explainable expected-vs-observed evidence.
4. Sensor-drift scenario handling.
5. Modular architecture ready for CAN/SocketCAN and higher-fidelity physics maps.

# Validation Strategy

Validate each layer, not only the dashboard.

1. **Health model:** accuracy, balanced accuracy, per-class precision/recall/F1. Prefer held-out flights rather than random adjacent rows.
2. **Anomaly model:** false alarms on healthy missions, anomaly separation and detection timing. Isolation Forest is trained only on healthy ACES telemetry.
3. **Digital Twin:** residual RMS, maximum absolute z-score and parameter-wise deviation.
4. **Fault injection:** verify expected signal direction for overheating, lubrication, misfire-like, injector, sensor drift and electrical scenarios.
5. **Mission replay:** record injected onset, first hybrid intelligent warning, first 3-sigma reference deviation, health/risk trajectories and sensor trust. Report timing honestly; do not force a positive lead-time result.
6. **RUL:** always show method, trend, confidence and domain limitation. Do not claim operational hours remaining without target-engine run-to-failure validation.
7. **Supporting data:** report CWRU and Marine metrics separately from ACES; they do not establish MALE-UAV accuracy.

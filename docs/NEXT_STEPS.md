# Next Engineering Steps

## Highest priority

1. Replace demonstrator mission-response functions with a stronger physics/thermodynamic aero-piston model.
2. Add real telemetry ingestion adapter using CAN/SocketCAN when hardware/logs are available.
3. Collect or obtain target-domain degradation/run-to-failure sequences for operational RUL development.
4. Add vibration features from a target-engine accelerometer/test rig instead of relying only on CWRU methodology.
5. Add injection-timing/ECU parameters when the target ECU schema is available.

## Product maturity

- persistent mission storage and searchable replay
- fleet-level health comparison
- authenticated operator/maintenance roles
- audit logging
- secure telemetry transport
- edge-inference packaging
- model-drift monitoring

## SIH priority rule

Do not add federated learning, 3D graphics or cloud complexity until the core chain is demonstrably working:

`telemetry → twin → residual → AI → diagnosis → degradation → mission decision`

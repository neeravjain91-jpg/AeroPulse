# Next Engineering Steps

1. Replace demonstrator mission-response functions with validated aero-piston thermodynamic/performance maps.
2. Add real ECU/FADEC telemetry through CAN/SocketCAN when hardware/logs are available.
3. Obtain target-domain degradation/run-to-failure sequences for operational RUL development.
4. Add target-engine accelerometer/vibration data instead of relying only on CWRU methodology.
5. Add injection-timing/ECU fields when the target schema is available.
6. Add persistent mission storage, fleet analytics, roles, audit logging, secure telemetry and edge packaging.

SIH priority: do not add federated learning, 3D graphics or cloud complexity until `telemetry → twin → residual → AI → diagnosis → degradation → mission decision` works end-to-end.

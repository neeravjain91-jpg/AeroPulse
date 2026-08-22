# Next build stages

## Priority 1 — Mission replay
- preserve timestamped sequences
- timeline scrubber
- first-anomaly marker
- threshold-vs-AI lead-time comparison

## Priority 2 — Better physics layer
- obtain target aero-piston performance maps or validated simulation data
- model altitude, mixture, cooling and throttle-transient behaviour
- calibrate reference state by mission/engine phase

## Priority 3 — RUL
Current datasets do not yet provide a clean target-engine run-to-failure/RUL label. Do not fabricate an operational RUL model. Add a suitable degradation/run-to-failure dataset or a clearly labelled simulated degradation benchmark and report uncertainty.

## Priority 4 — CAN/edge
- python-can + SocketCAN adapter
- telemetry schema validation
- local inference container
- secure GCS channel

## Priority 5 — Validation
- mission/group-level split
- false alarm rate
- detection lead time
- calibration
- missing-sensor/noise robustness

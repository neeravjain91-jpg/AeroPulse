# RUL Data Plan

## Current limitation

The supplied datasets do not provide a clean, validated MALE-UAV aero-piston engine run-to-failure target suitable for operational RUL training.

## Current implementation

Mission Replay computes a **prototype degradation horizon** by fitting a recent health-index trend and extrapolating toward a defined critical health-index boundary. The output includes confidence and a clear method limitation.

## Optional methodology benchmark

Use `scripts/train_rul_cmapss.py` with NASA C-MAPSS-style files to validate RUL modelling workflow and error metrics on a run-to-failure benchmark.

This must remain a separate methodology result because C-MAPSS represents turbofan degradation, not the target piston engine.

## Target-domain data eventually needed

- engine/unit identifier
- timestamps/cycles/flight hours
- mission/operating condition
- calibrated sensor telemetry
- maintenance actions
- known degradation/fault onset
- component replacement/removal reason
- failure/end-of-life criterion

Only then should AeroPulse-X claim target-engine RUL performance.

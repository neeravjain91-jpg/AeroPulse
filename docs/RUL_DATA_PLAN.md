# RUL Data Plan

The supplied datasets do not provide a clean validated MALE-UAV aero-piston run-to-failure target.

Current runtime: Mission Replay fits a recent health-index trend and extrapolates toward a critical health-index boundary. It returns method, trend and confidence and is explicitly labelled a demonstrator.

Optional methodology benchmark: `scripts/train_rul_cmapss.py` can use NASA C-MAPSS-style files to validate an RUL workflow. C-MAPSS is turbofan data, so this must remain separate methodology evidence.

Target-domain RUL eventually needs engine/unit ID, cycles/flight hours, mission condition, calibrated telemetry, maintenance actions, fault onset, replacement/removal reason and an end-of-life criterion.

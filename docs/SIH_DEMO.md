# Recommended SIH Live Demo

## Demo 1 — Healthy mission

1. Select `CRUISE`, no fault.
2. Run snapshot at a moderate altitude/temperature.
3. Show:
   - Normal/healthy state
   - high sensor trust
   - low mission risk
   - small expected-vs-observed residuals

Message: **the twin understands normal engine behaviour in mission context.**

## Demo 2 — Lubrication degradation

1. Select `lubrication` at severity ~0.7–0.8.
2. Run Mission Replay.
3. Show:
   - oil pressure trending down
   - oil temperature trending up
   - Digital Twin residual increasing
   - fault evidence: lubrication degradation
   - health/risk timeline
   - maintenance advisory
   - RUL method demonstrator if the trend is sufficiently degrading

Message: **we detect a developing pattern, not only a single hard threshold.**

## Demo 3 — Sensor drift

1. Select `sensor_drift`.
2. Run snapshot/replay.
3. Show the sensor-trust module flagging inconsistent water-temperature behaviour.

Message: **AeroPulse-X tries to distinguish instrumentation issues from real engine degradation.**

## Demo 4 — Mission awareness

Keep engine/fault settings fixed, then compare:

- low-altitude / normal-temperature / short mission
- high-altitude / hot-weather / endurance mission

Show the mission-risk breakdown changing.

Message: **the same engine health does not imply the same mission risk under every operating condition.**

## Judge-ready one-line explanation

> “Instead of waiting for a parameter to cross a limit, AeroPulse-X builds a synchronized expected engine state, measures deviation, combines AI with cross-sensor evidence, tracks degradation, replays mission behaviour and converts engine condition into explainable maintenance and mission-risk decision support.”

## Claims to avoid

Do not say:

- “99% accurate real UAV failure prediction”
- “DRDO-grade certified engine model”
- “real MALE UAV telemetry” unless you actually have it
- “CWRU/Marine proves our UAV engine faults”
- “our RUL is operationally validated”

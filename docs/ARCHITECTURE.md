# AeroPulse-X Architecture

## 1. Design principle

The Digital Twin is the **central intelligence layer**, not a 3D graphic. It maintains a healthy reference for the current operating state, adjusts that reference for the simulated mission context, and measures how the observed engine deviates from expected behaviour.

## 2. End-to-end architecture

```text
ECU / FADEC / CAN / simulated telemetry
                 ↓
        Data ingestion layer
                 ↓
     Validation + synchronization
                 ↓
        Mission-context model
                 ↓
 ┌──────────── DIGITAL TWIN ──────────────┐
 │ Healthy operating-state reference       │
 │ + altitude / ambient / endurance        │
 │ + rapid-throttle context adjustment     │
 └──────────────────┬───────────────────────┘
                    ↓
          Expected ↔ Observed
                    ↓
       Residuals / z-scores / Δ%
                    ↓
 ┌──────────────────┼──────────────────┐
 ↓                  ↓                  ↓
Health AI      Isolation Forest   Sensor trust
 ↓                  ↓                  ↓
 └──────────────────┼──────────────────┘
                    ↓
         Fault evidence engine
                    ↓
      Degradation / trend tracking
                    ↓
       Mission replay + risk model
                    ↓
       Maintenance decision support
                    ↓
             GCS dashboard
```

## 3. Primary data path

The ACES UAV dataset is the primary runtime-development source. Raw sensor features are used; derived anomaly labels/scores are excluded from model inputs to prevent target leakage.

The richer training path uses held-out **Flight** groups for test evaluation, reducing temporal/group leakage compared with random row splitting.

## 4. Supporting models

### CWRU
Used as a separate bearing/vibration-condition research module. It is never concatenated row-wise with ACES telemetry.

### Marine Engine Fault
Used for fault-signature experimentation only. The supplied held-out condition generalization is weak, so this model is intentionally not used as authoritative MALE-UAV diagnosis.

## 5. Mission-aware twin

The simulator and Digital Twin use the same transparent demonstrator response functions for:

- altitude
- ambient temperature
- endurance duration
- rapid throttle transitions

This makes a healthy simulated mission compare against a context-adjusted expected reference instead of incorrectly treating every environmental effect as a fault.

These response functions must later be replaced by validated thermodynamic/performance maps for the target aero-piston engine.

## 6. Sensor trust

Sensor-trust logic uses cross-sensor consistency, for example:

- one EGT channel deviates while peer EGT channels remain normal
- water temperature deviates without corroborating EGT/oil-temperature change
- oil pressure moves strongly without supporting lubrication-state evidence

The output is a decision-support suspicion score, not a certified sensor-failure declaration.

## 7. Mission risk

Mission risk is an explainable prototype index combining:

- current engine condition
- Digital Twin deviation
- mission stress
- fault evidence
- sensor uncertainty

The output is deliberately called a **mission-risk index / mission-reliability index**, not a probability of mission success.

## 8. RUL

Runtime RUL is a trend-extrapolation method demonstrator over mission replay health history. Operational RUL requires target-engine degradation/run-to-failure evidence.

An optional C-MAPSS trainer is included solely to validate the RUL modelling methodology on an established run-to-failure benchmark.

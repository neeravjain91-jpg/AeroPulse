# AeroPulse-X Architecture

The Digital Twin is the central intelligence layer, not a 3D graphic.

```text
ECU / FADEC / CAN / simulated telemetry
                 ↓
        validation + synchronization
                 ↓
       mission-context model
                 ↓
   context-aware healthy Digital Twin
                 ↓
        Expected ↔ Observed
                 ↓
 residuals / z-scores / percentage deviation
                 ↓
 Health AI + Isolation Forest + Sensor trust
                 ↓
       fault evidence engine
                 ↓
 degradation / mission replay / risk
                 ↓
 maintenance decision support + GCS
```

ACES is the primary UAV dataset. CWRU remains a separate vibration/bearing methodology module. Marine Engine data remain supporting fault-signature research because the supplied cross-condition generalization is weak. These datasets are not concatenated row-by-row.

The mission-context response functions are transparent demonstrator functions and must later be replaced by validated aero-piston thermodynamic/performance maps. Runtime RUL is likewise a method demonstrator until target-domain run-to-failure data are available.

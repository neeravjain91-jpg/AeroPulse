# Validation Strategy

## Core principle

Do not prove the project by showing only a dashboard. Validate each layer separately.

## 1. Health classifier

Recommended metrics:

- accuracy
- balanced accuracy
- per-class precision / recall / F1
- confusion matrix

Preferred split: **held-out flights**, not random adjacent telemetry rows.

## 2. Anomaly detector

Evaluate:

- false-alarm rate on healthy held-out missions
- anomaly score separation
- first-detection time in controlled fault scenarios

The current Isolation Forest is trained only on healthy ACES telemetry.

## 3. Digital Twin

Evaluate expected vs observed response using:

- residual RMS
- maximum absolute z-score
- parameter-wise percentage deviation

A healthy mission scenario should remain close to its context-adjusted reference. Fault injection should create increasing residuals.

## 4. Fault-injection tests

Controlled software faults:

| Fault | Expected direction |
|---|---|
| Overheating | EGT/CHT/water/oil temperature rise |
| Lubrication | oil pressure falls, oil temperature rises |
| Misfire-like | RPM/EGT imbalance |
| Injector | fuel-flow/MAP/EGT inconsistency |
| Sensor drift | isolated water-temperature shift |
| Electrical | battery voltage degrades, electrical/alternator signals change |

These are controlled demonstrator response functions, not a certified failure model.

## 5. Mission replay

For each replay record:

- injected fault onset
- first AI warning
- first 3-sigma reference deviation
- health-index trajectory
- mission-risk trajectory
- sensor-trust trajectory

Do not force a positive “early warning gain.” Report the measured timing honestly.

## 6. RUL

The runtime RUL result must always be presented with:

- method name
- trend slope
- confidence
- data limitation note

Do not state “47 hours remaining” as a real engine-life prediction unless validated target-engine run-to-failure data support it.

## 7. Supporting-domain models

CWRU and Marine results must be reported separately from ACES. They do not establish MALE-UAV engine accuracy.

from __future__ import annotations

import joblib
import numpy as np
import pandas as pd

from .advisory import fault_advisory, maintenance_advice
from .config import MODEL_DIR
from .digital_twin import PARAMS, ReferenceTwin

HEALTH_ORDER = {"Normal": 0, "Watch": 1, "Warning": 2, "Critical": 3}


class AeroTwinAI:
    def __init__(self):
        self.health = joblib.load(MODEL_DIR / "aces_health.joblib")
        self.anomaly = joblib.load(MODEL_DIR / "aces_anomaly.joblib")
        self.twin = ReferenceTwin()

    def analyze(self, telemetry: dict):
        columns = PARAMS + ["Operating_State"]
        health_frame = pd.DataFrame([{column: telemetry[column] for column in columns}])

        probability = self.health.predict_proba(health_frame)[0]
        classes = self.health.classes_
        prediction = str(classes[int(np.argmax(probability))])
        probabilities = {str(label): float(value) for label, value in zip(classes, probability)}

        anomaly_frame = pd.DataFrame([{parameter: telemetry[parameter] for parameter in PARAMS}])
        anomaly_score = float(-self.anomaly.decision_function(anomaly_frame)[0])

        twin = self.twin.compare(telemetry)
        findings = fault_advisory(telemetry, twin)
        health_index = max(
            0.0,
            100.0
            - (
                HEALTH_ORDER.get(prediction, 1) * 22
                + min(twin["residual_rms"], 10) * 2.0
            ),
        )

        return {
            "health_state": prediction,
            "health_probabilities": probabilities,
            "health_index": round(health_index, 1),
            "anomaly_score": round(anomaly_score, 4),
            "twin": twin,
            "fault_candidates": [
                {"name": name, "severity": severity, "evidence": evidence}
                for name, severity, evidence in findings
            ],
            "maintenance_advisory": maintenance_advice(findings),
            "disclaimer": "Prototype decision-support output; not an airworthiness or flight-safety determination.",
        }

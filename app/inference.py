from __future__ import annotations

import joblib
import numpy as np
import pandas as pd

from .advisory import fault_advisory, maintenance_advice
from .config import MODEL_DIR
from .digital_twin import PARAMS, ReferenceTwin
from .rul_service import RULService
from .sensor_health import assess_sensor_health


HEALTH_ORDER = {
    "Normal": 0,
    "Watch": 1,
    "Warning": 2,
    "Critical": 3,
}


class AeroTwinAI:
    def __init__(self):
        self.health = joblib.load(
            MODEL_DIR / "aces_health.joblib"
        )

        self.anomaly = joblib.load(
            MODEL_DIR / "aces_anomaly.joblib"
        )

        self.twin = ReferenceTwin()

        self.rul = RULService()

    def analyze(
        self,
        telemetry: dict,
        context: dict | None = None,
    ):
        columns = PARAMS + [
            "Operating_State"
        ]

        missing = [
            column
            for column in columns
            if column not in telemetry
        ]

        if missing:
            raise ValueError(
                f"Missing telemetry fields: {missing}"
            )

        # ---------------------------------------------------------
        # ML HEALTH CLASSIFICATION
        # ---------------------------------------------------------

        health_frame = pd.DataFrame(
            [
                {
                    column: telemetry[column]
                    for column in columns
                }
            ]
        )

        probability = self.health.predict_proba(
            health_frame
        )[0]

        classes = self.health.classes_

        prediction = str(
            classes[
                int(
                    np.argmax(probability)
                )
            ]
        )

        probabilities = {
            str(label): float(value)
            for label, value in zip(
                classes,
                probability,
            )
        }

        # ---------------------------------------------------------
        # ANOMALY DETECTION
        # ---------------------------------------------------------

        anomaly_frame = pd.DataFrame(
            [
                {
                    parameter: telemetry[
                        parameter
                    ]
                    for parameter in PARAMS
                }
            ]
        )

        anomaly_score = float(
            -self.anomaly.decision_function(
                anomaly_frame
            )[0]
        )

        # ---------------------------------------------------------
        # DIGITAL TWIN
        # ---------------------------------------------------------

        twin = self.twin.compare(
            telemetry,
            context=context,
        )

        anomaly_flag = (
            anomaly_score > 0.005
            and float(
                twin["residual_rms"]
            ) >= 2.0
        )

        # ---------------------------------------------------------
        # SENSOR HEALTH
        # ---------------------------------------------------------

        sensor_health = assess_sensor_health(
            telemetry,
            twin,
        )

        # ---------------------------------------------------------
        # FAULT EVIDENCE
        # ---------------------------------------------------------

        findings = fault_advisory(
            telemetry,
            twin,
            sensor_health,
        )

        # ---------------------------------------------------------
        # BASE HEALTH INDEX
        #
        # This preserves the existing ML + Digital-Twin logic.
        # ---------------------------------------------------------

        base_health_index = (
            100.0
            - HEALTH_ORDER.get(
                prediction,
                1,
            )
            * 18.0
            - min(
                float(
                    twin["residual_rms"]
                ),
                12.0,
            )
            * 4.0
            - max(
                0.0,
                100.0
                - sensor_health[
                    "overall_trust_score"
                ],
            )
            * 0.10
        )

        base_health_index = max(
            0.0,
            min(
                100.0,
                base_health_index,
            ),
        )

        # ---------------------------------------------------------
        # EXPLICIT DEGRADATION CONTRIBUTION
        #
        # Replay inject_fault() exposes:
        #
        #     Degradation_Severity
        #
        # This value represents the progression of the injected
        # fault through the replay. It must influence the health
        # trajectory; otherwise RUL has no meaningful degradation
        # trajectory to estimate.
        #
        # We deliberately keep this contribution bounded and
        # transparent. It is a prototype simulation mechanism,
        # NOT a physical engine-health model.
        # ---------------------------------------------------------

        degradation_severity = max(
            0.0,
            min(
                1.0,
                float(
                    telemetry.get(
                        "Degradation_Severity",
                        0.0,
                    )
                ),
            ),
        )

        degradation_penalty = (
            degradation_severity
            * 45.0
        )

        health_index_value = (
            base_health_index
            - degradation_penalty
        )

        health_index_value = max(
            0.0,
            min(
                100.0,
                health_index_value,
            ),
        )

        # ---------------------------------------------------------
        # FUSED HEALTH STATE
        # ---------------------------------------------------------

        if health_index_value >= 85:
            fused_state = "Normal"

        elif health_index_value >= 65:
            fused_state = "Watch"

        elif health_index_value >= 40:
            fused_state = "Warning"

        else:
            fused_state = "Critical"

        confidence = float(
            max(probability)
        )

        # ---------------------------------------------------------
        # RUL
        # ---------------------------------------------------------

        rul = self.rul.predict(
            telemetry,
            context=context,
        )

        # ---------------------------------------------------------
        # RESPONSE
        # ---------------------------------------------------------

        return {
            "health_state": fused_state,

            "ml_health_state": prediction,

            "health_confidence": round(
                confidence,
                4,
            ),

            "health_probabilities":
                probabilities,

            "health_index": round(
                health_index_value,
                1,
            ),

            "base_health_index": round(
                base_health_index,
                1,
            ),

            "degradation_severity": round(
                degradation_severity,
                4,
            ),

            "degradation_penalty": round(
                degradation_penalty,
                2,
            ),

            "anomaly_score": round(
                anomaly_score,
                4,
            ),

            "anomaly_flag": anomaly_flag,

            "twin": twin,

            "sensor_health": sensor_health,

            "rul": rul,

            "fault_candidates": [
                {
                    "name": name,
                    "severity": severity,
                    "evidence": evidence,
                }
                for name, severity, evidence
                in findings
            ],

            "maintenance_advisory":
                maintenance_advice(
                    findings,
                    sensor_health,
                ),

            "disclaimer": (
                "Prototype decision-support output; "
                "not an airworthiness or flight-safety "
                "determination."
            ),
        }
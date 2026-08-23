from __future__ import annotations

import joblib
import pandas as pd

from .config import DATA_SAMPLE_DIR, MODEL_DIR


class VibrationAI:
    """Supporting CWRU vibration/bearing condition classifier.

    It is intentionally isolated from the ACES engine-health model because the
    datasets come from different platforms and sensing domains.
    """

    def __init__(self):
        payload = joblib.load(MODEL_DIR / "cwru_vibration.joblib")
        self.model = payload["model"]
        self.features = payload["features"]

    def analyze(self, features: dict) -> dict:
        missing = [f for f in self.features if f not in features]
        if missing:
            raise ValueError(f"Missing vibration features: {missing}")
        frame = pd.DataFrame([{f: features[f] for f in self.features}])
        prediction = str(self.model.predict(frame)[0])
        probabilities = None
        confidence = None
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(frame)[0]
            probabilities = {
                str(label): round(float(value), 5)
                for label, value in zip(self.model.classes_, proba)
            }
            confidence = round(max(probabilities.values()), 5)
        return {
            "predicted_condition": prediction,
            "confidence": confidence,
            "probabilities": probabilities,
            "role": "Supporting vibration/bearing-condition module trained on CWRU data; not MALE-UAV validation.",
        }


def load_demo() -> pd.DataFrame | None:
    path = DATA_SAMPLE_DIR / "cwru_demo.csv"
    return pd.read_csv(path) if path.exists() else None

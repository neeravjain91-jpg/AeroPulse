from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models"
STATIC_DIR = ROOT / "static"
DATA_SAMPLE_DIR = ROOT / "data_sample"

PROJECT_NAME = "AeroPulse-X"
PROJECT_VERSION = "1.0.0-sih"

REQUIRED_MODEL_FILES = (
    "aces_health.joblib",
    "aces_anomaly.joblib",
    "healthy_reference.json",
)

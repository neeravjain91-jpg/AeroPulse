from pathlib import Path

import pytest

from app.config import MODEL_DIR, REQUIRED_MODEL_FILES
from app.inference import AeroTwinAI


def test_models_load_when_assets_exist():
    if not all((MODEL_DIR / name).exists() for name in REQUIRED_MODEL_FILES):
        pytest.skip("Model artifacts are generated locally and are not committed to Git.")
    AeroTwinAI()

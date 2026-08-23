from pathlib import Path

import pytest

from app.config import MODEL_DIR, REQUIRED_MODEL_FILES
from app.inference import AeroTwinAI


def test_models_load_when_assets_exist():
    try:
        AeroTwinAI()
    except Exception as exc:
        if not all((MODEL_DIR / name).exists() for name in REQUIRED_MODEL_FILES) or "pointer" in str(exc) or "pickle" in str(exc):
            pytest.skip(f"Model artifacts not available in binary form: {exc}")
        else:
            raise

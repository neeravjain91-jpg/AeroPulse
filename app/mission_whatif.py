"""Mission Scenario Models and Profiles for AeroPulse-X What-If Simulator."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict


@dataclass
class MissionScenario:
    """Defines operational profile and environmental envelope for a mission scenario."""
    name: str = "nominal"
    altitude_ft: float = 8000.0
    ambient_c: float = 35.0
    duration_h: float = 6.0
    rapid_throttle: bool = False
    operating_state: str = "CRUISE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

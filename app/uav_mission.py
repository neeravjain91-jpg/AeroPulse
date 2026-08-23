from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class MissionPoint:
    """
    One simulated UAV mission state.

    This is a mission-level abstraction for the SIH prototype.
    It is not a certified flight-dynamics model.
    """

    step: int
    time_min: float
    mission_phase: str
    altitude_ft: float
    ambient_c: float
    throttle: float
    load: float
    operating_state: str
    rapid_throttle: bool


class UAVMissionSimulator:
    """
    Generates a deterministic UAV mission profile for the AeroPulse-X
    propulsion-monitoring demonstrator.

    The simulator represents the flight/environment conditions that drive
    the existing reduced-order engine model.

    Mission profile:

        TAKEOFF
          ↓
        CLIMB
          ↓
        CRUISE
          ↓
        HIGH_ALTITUDE
          ↓
        ENDURANCE
          ↓
        DESCENT
          ↓
        LANDING
    """

    def __init__(
        self,
        duration_min: float = 30.0,
        max_altitude_ft: float = 20000.0,
        cruise_altitude_ft: float = 8000.0,
        ambient_c: float = 35.0,
        hot_weather: bool = False,
        rapid_throttle: bool = False,
    ):
        self.duration_min = max(5.0, float(duration_min))
        self.max_altitude_ft = max(3000.0, float(max_altitude_ft))
        self.cruise_altitude_ft = max(
            1000.0,
            min(float(cruise_altitude_ft), self.max_altitude_ft),
        )
        self.ambient_c = float(ambient_c)
        self.hot_weather = bool(hot_weather)
        self.rapid_throttle = bool(rapid_throttle)

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _phase(self, ratio: float) -> str:
        """
        Determine mission phase from normalized mission progress.
        """

        if ratio < 0.08:
            return "TAKEOFF"

        if ratio < 0.20:
            return "CLIMB"

        if ratio < 0.45:
            return "CRUISE"

        if ratio < 0.70:
            return "HIGH_ALTITUDE"

        if ratio < 0.86:
            return "ENDURANCE"

        if ratio < 0.96:
            return "DESCENT"

        return "LANDING"

    def _altitude(self, ratio: float, phase: str) -> float:
        """
        Generate altitude according to mission phase.
        """

        if phase == "TAKEOFF":
            local = ratio / 0.08
            return self.cruise_altitude_ft * local

        if phase == "CLIMB":
            local = (ratio - 0.08) / 0.12
            return self.cruise_altitude_ft + (
                self.max_altitude_ft - self.cruise_altitude_ft
            ) * local

        if phase == "CRUISE":
            oscillation = math.sin(ratio * math.pi * 8.0) * 150.0
            return self.cruise_altitude_ft + oscillation

        if phase == "HIGH_ALTITUDE":
            oscillation = math.sin(ratio * math.pi * 10.0) * 250.0
            return self.max_altitude_ft + oscillation

        if phase == "ENDURANCE":
            oscillation = math.sin(ratio * math.pi * 6.0) * 180.0
            return self.cruise_altitude_ft + oscillation

        if phase == "DESCENT":
            local = (ratio - 0.86) / 0.10
            local = self._clamp(local, 0.0, 1.0)
            return self.max_altitude_ft + (
                self.cruise_altitude_ft - self.max_altitude_ft
            ) * local

        # LANDING
        local = (ratio - 0.96) / 0.04
        local = self._clamp(local, 0.0, 1.0)
        return self.cruise_altitude_ft * (1.0 - local)

    def _throttle(self, ratio: float, phase: str) -> float:
        """
        Generate mission throttle demand.
        """

        if phase == "TAKEOFF":
            return 0.82

        if phase == "CLIMB":
            return 0.76

        if phase == "CRUISE":
            base = 0.60
            variation = 0.04 * math.sin(ratio * math.pi * 10.0)
            return self._clamp(base + variation, 0.50, 0.72)

        if phase == "HIGH_ALTITUDE":
            base = 0.70
            variation = 0.05 * math.sin(ratio * math.pi * 8.0)
            return self._clamp(base + variation, 0.60, 0.82)

        if phase == "ENDURANCE":
            base = 0.56
            variation = 0.03 * math.sin(ratio * math.pi * 12.0)
            return self._clamp(base + variation, 0.48, 0.64)

        if phase == "DESCENT":
            return 0.42

        return 0.30

    def _load(self, throttle: float, phase: str) -> float:
        """
        Approximate engine load from mission demand.
        """

        phase_factor = {
            "TAKEOFF": 1.05,
            "CLIMB": 1.00,
            "CRUISE": 0.92,
            "HIGH_ALTITUDE": 0.98,
            "ENDURANCE": 0.84,
            "DESCENT": 0.65,
            "LANDING": 0.45,
        }.get(phase, 0.90)

        load = throttle * phase_factor

        return self._clamp(load, 0.20, 1.10)

    def _ambient_temperature(self, ratio: float, altitude_ft: float) -> float:
        """
        Simple environmental temperature model.

        Hot-weather mode intentionally raises the ground/mission temperature.
        Altitude introduces a basic lapse-rate effect.
        """

        base = self.ambient_c

        if self.hot_weather:
            base += 8.0

        altitude_effect = altitude_ft / 1000.0 * 1.8

        temperature = base - altitude_effect

        # Small deterministic environmental variation.
        variation = 1.5 * math.sin(ratio * math.pi * 6.0)

        return round(temperature + variation, 2)

    def _operating_state(self, phase: str) -> str:
        """
        Map mission phase to the existing AeroPulse operating-state vocabulary.
        """

        if phase in {"TAKEOFF", "CLIMB", "HIGH_ALTITUDE"}:
            return "HIGH"

        if phase == "ENDURANCE":
            return "CRUISE_LOW"

        return "CRUISE"

    def _rapid_throttle_event(self, ratio: float) -> bool:
        """
        Produce controlled throttle-transition events.

        These events are useful for demonstrating transient engine behavior.
        """

        if not self.rapid_throttle:
            return False

        # Two deterministic transient windows.
        event_1 = 0.30 <= ratio <= 0.34
        event_2 = 0.62 <= ratio <= 0.66

        return event_1 or event_2

    def point(self, step: int, total_steps: int) -> MissionPoint:
        """
        Generate one mission point.
        """

        total_steps = max(1, int(total_steps))
        step = max(0, min(int(step), total_steps - 1))

        ratio = step / max(1, total_steps - 1)
        time_min = ratio * self.duration_min

        phase = self._phase(ratio)
        altitude = self._altitude(ratio, phase)

        throttle = self._throttle(ratio, phase)

        rapid_event = self._rapid_throttle_event(ratio)

        if rapid_event:
            # Deliberate transient demand.
            throttle = self._clamp(throttle + 0.14, 0.20, 1.0)

        load = self._load(throttle, phase)

        ambient = self._ambient_temperature(
            ratio,
            altitude,
        )

        return MissionPoint(
            step=step,
            time_min=round(time_min, 3),
            mission_phase=phase,
            altitude_ft=round(altitude, 2),
            ambient_c=round(ambient, 2),
            throttle=round(throttle, 4),
            load=round(load, 4),
            operating_state=self._operating_state(phase),
            rapid_throttle=rapid_event,
        )

    def generate(self, steps: int = 120) -> list[MissionPoint]:
        """
        Generate an entire deterministic mission.
        """

        steps = max(12, min(int(steps), 360))

        return [
            self.point(step=index, total_steps=steps)
            for index in range(steps)
        ]

    def current_context(self, step: int, total_steps: int = 120) -> dict:
        """
        Return the current mission state as a dictionary suitable for
        feeding into the existing simulator/API.
        """

        point = self.point(step, total_steps)

        return {
            "step": point.step,
            "time_min": point.time_min,
            "mission_phase": point.mission_phase,
            "altitude_ft": point.altitude_ft,
            "ambient_c": point.ambient_c,
            "throttle": point.throttle,
            "load": point.load,
            "operating_state": point.operating_state,
            "rapid_throttle": point.rapid_throttle,
        }
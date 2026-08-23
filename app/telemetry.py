from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


TELEMETRY_VERSION = "1.0"


SENSOR_FIELDS = [
    "Engine_RPM",
    "EGT1",
    "EGT2",
    "EGT3",
    "CHT",
    "Fuel_Flow",
    "Oil_Temp",
    "Oil_Pressure",
    "Battery_Voltage",
    "Battery_Current",
    "Alternator_Temp",
    "EFI_Fuel_Temp",
    "EFI_Water_Temp",
    "MAP_Injector",
    "Vibration",
    "Efficiency",
    "Load",
    "Air_Density_Ratio",
]


MISSION_FIELDS = [
    "Mission_Phase",
    "Mission_Time_Min",
    "Mission_Step",
    "Altitude_ft",
    "Ambient_C",
    "Throttle",
    "Operating_State",
    "Rapid_Throttle",
]


@dataclass
class UAVTelemetry:
    """
    Hardware-equivalent UAV propulsion telemetry packet.

    This is the common interface between:

        Real UAV / ECU / CAN
                    OR
        UAV simulator

    and the AeroPulse analytics pipeline.
    """

    Engine_RPM: float
    EGT1: float
    EGT2: float
    EGT3: float
    CHT: float
    Fuel_Flow: float
    Oil_Temp: float
    Oil_Pressure: float
    Battery_Voltage: float
    Battery_Current: float
    Alternator_Temp: float
    EFI_Fuel_Temp: float
    EFI_Water_Temp: float
    MAP_Injector: float
    Vibration: float
    Efficiency: float
    Load: float
    Air_Density_Ratio: float

    Mission_Phase: str = "UNKNOWN"
    Mission_Time_Min: float = 0.0
    Mission_Step: int = 0
    Altitude_ft: float = 0.0
    Ambient_C: float = 25.0
    Throttle: float = 0.0
    Operating_State: str = "CRUISE"
    Rapid_Throttle: bool = False

    telemetry_version: str = TELEMETRY_VERSION
    source: str = "uav_simulator"

    def to_dict(self) -> dict[str, Any]:
        """
        Convert telemetry packet to a JSON-compatible dictionary.
        """

        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "UAVTelemetry":
        """
        Construct a telemetry packet from a dictionary.

        This is the interface that will later allow us to
        accept CAN/ECU/serial telemetry.
        """

        missing = [
            field
            for field in SENSOR_FIELDS
            if field not in data
        ]

        if missing:
            raise ValueError(
                f"Missing required telemetry fields: {missing}"
            )

        values = {
            field: data[field]
            for field in SENSOR_FIELDS
        }

        for field in MISSION_FIELDS:
            if field in data:
                values[field] = data[field]

        return cls(**values)

    def validate(self) -> None:
        """
        Validate the telemetry packet before it enters
        the Digital Twin / AI pipeline.
        """

        required_numeric = SENSOR_FIELDS + [
            "Mission_Time_Min",
            "Altitude_ft",
            "Ambient_C",
            "Throttle",
        ]

        for field in required_numeric:
            value = getattr(self, field)

            if not isinstance(
                value,
                (int, float),
            ):
                raise ValueError(
                    f"{field} must be numeric, "
                    f"got {type(value).__name__}"
                )

        if self.Engine_RPM < 0:
            raise ValueError(
                "Engine_RPM cannot be negative"
            )

        if self.Fuel_Flow < 0:
            raise ValueError(
                "Fuel_Flow cannot be negative"
            )

        if self.Oil_Pressure < 0:
            raise ValueError(
                "Oil_Pressure cannot be negative"
            )

        if self.Vibration < 0:
            raise ValueError(
                "Vibration cannot be negative"
            )

        if not 0.0 <= self.Throttle <= 1.0:
            raise ValueError(
                "Throttle must be between 0 and 1"
            )

        if not 0.0 <= self.Load <= 1.5:
            raise ValueError(
                "Load must be between 0 and 1.5"
            )

        if self.Altitude_ft < 0:
            raise ValueError(
                "Altitude_ft cannot be negative"
            )

    def sensor_dict(self) -> dict[str, float]:
        """
        Return only propulsion sensor values.

        This is what the Digital Twin / AI uses as
        the engine observation vector.
        """

        return {
            field: float(
                getattr(self, field)
            )
            for field in SENSOR_FIELDS
        }

    def mission_dict(self) -> dict[str, Any]:
        """
        Return mission/environment metadata.
        """

        return {
            field: getattr(self, field)
            for field in MISSION_FIELDS
        }


def telemetry_from_engine(
    engine_data: dict[str, Any],
    mission_point: Any,
    source: str = "uav_simulator",
) -> UAVTelemetry:
    """
    Convert ReducedOrderPistonEngine output + UAV mission
    state into a hardware-equivalent telemetry packet.
    """

    packet = UAVTelemetry(
        Engine_RPM=float(
            engine_data["Engine_RPM"]
        ),
        EGT1=float(
            engine_data["EGT1"]
        ),
        EGT2=float(
            engine_data["EGT2"]
        ),
        EGT3=float(
            engine_data["EGT3"]
        ),
        CHT=float(
            engine_data["CHT"]
        ),
        Fuel_Flow=float(
            engine_data["Fuel_Flow"]
        ),
        Oil_Temp=float(
            engine_data["Oil_Temp"]
        ),
        Oil_Pressure=float(
            engine_data["Oil_Pressure"]
        ),
        Battery_Voltage=float(
            engine_data["Battery_Voltage"]
        ),
        Battery_Current=float(
            engine_data["Battery_Current"]
        ),
        Alternator_Temp=float(
            engine_data["Alternator_Temp"]
        ),
        EFI_Fuel_Temp=float(
            engine_data["EFI_Fuel_Temp"]
        ),
        EFI_Water_Temp=float(
            engine_data["EFI_Water_Temp"]
        ),
        MAP_Injector=float(
            engine_data["MAP_Injector"]
        ),
        Vibration=float(
            engine_data["Vibration"]
        ),
        Efficiency=float(
            engine_data["Efficiency"]
        ),
        Load=float(
            engine_data["Load"]
        ),
        Air_Density_Ratio=float(
            engine_data["Air_Density_Ratio"]
        ),
        Mission_Phase=str(
            mission_point.mission_phase
        ),
        Mission_Time_Min=float(
            mission_point.time_min
        ),
        Mission_Step=int(
            mission_point.step
        ),
        Altitude_ft=float(
            mission_point.altitude_ft
        ),
        Ambient_C=float(
            mission_point.ambient_c
        ),
        Throttle=float(
            mission_point.throttle
        ),
        Operating_State=str(
            mission_point.operating_state
        ),
        Rapid_Throttle=bool(
            mission_point.rapid_throttle
        ),
        telemetry_version=TELEMETRY_VERSION,
        source=source,
    )

    packet.validate()

    return packet
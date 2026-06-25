"""Contract helpers for /sensor/raw.

/sensor/raw is the ESP32 → RPi raw PIR/ToF message.
ESP32 does not provide a timestamp. RPi attaches the authoritative receive time.
CSI is intentionally not included here. CSI must be received on the RPi side
through Nexmon CSI UDP/pcap utilities and then fused later by the preprocessing
team.
"""

from typing import Any, Dict, List

REQUIRED_TOP_LEVEL_FIELDS = {
    "type",
    "source",
    "deviceId",
    "seq",
    "sampleIntervalMs",
    "sensors",
}

REQUIRED_SENSOR_FIELDS = {
    "pirMotion",
    "pirValue",
    "tofDistanceMm",
    "tofValid",
    "tofTimeout",
    "tofError",
}


def validate_sensor_raw(payload: Dict[str, Any]) -> List[str]:
    """Return validation error messages. Empty list means the payload is usable."""
    errors: List[str] = []

    missing_top = sorted(REQUIRED_TOP_LEVEL_FIELDS - payload.keys())
    if missing_top:
        errors.append(f"missing top-level fields: {missing_top}")

    if payload.get("type") != "sensor.raw":
        errors.append("type must be 'sensor.raw'")

    sensors = payload.get("sensors")
    if not isinstance(sensors, dict):
        errors.append("sensors must be an object")
        return errors

    missing_sensor = sorted(REQUIRED_SENSOR_FIELDS - sensors.keys())
    if missing_sensor:
        errors.append(f"missing sensors fields: {missing_sensor}")

    if "pirMotion" in sensors and not isinstance(sensors["pirMotion"], bool):
        errors.append("sensors.pirMotion must be boolean")

    if "pirValue" in sensors and sensors["pirValue"] not in (0, 1):
        errors.append("sensors.pirValue must be 0 or 1")

    tof_valid = sensors.get("tofValid")
    if "tofValid" in sensors and not isinstance(tof_valid, bool):
        errors.append("sensors.tofValid must be boolean")

    tof_distance = sensors.get("tofDistanceMm")
    if tof_valid is True:
        if not isinstance(tof_distance, int) or tof_distance < 0:
            errors.append("sensors.tofDistanceMm must be a non-negative integer when tofValid=true")
    else:
        if tof_distance is not None:
            errors.append("sensors.tofDistanceMm must be null when tofValid=false")

    return errors

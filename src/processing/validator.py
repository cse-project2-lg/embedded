from __future__ import annotations

from typing import Dict, Any, Tuple, List


def validate_raw_message(message: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    required_top = ["messageId", "timestamp", "type", "source", "deviceId", "payload"]
    for key in required_top:
        if key not in message:
            errors.append(f"missing top-level field: {key}")

    payload = message.get("payload", {})
    for sensor_key in ["csi", "pir", "tof"]:
        if sensor_key not in payload:
            errors.append(f"missing payload field: {sensor_key}")

    tof = payload.get("tof", {})
    distance = tof.get("distanceMm")
    if distance is None:
        errors.append("missing tof.distanceMm")
    elif not isinstance(distance, int):
        errors.append("tof.distanceMm must be int")
    elif distance < 0:
        errors.append("tof.distanceMm must be non-negative")

    pir = payload.get("pir", {})
    motion = pir.get("motion")
    if motion not in [0, 1, True, False]:
        errors.append("pir.motion must be 0/1 or bool")

    csi = payload.get("csi", {})
    change = csi.get("change")
    if change is not None and not isinstance(change, (int, float)):
        errors.append("csi.change must be numeric")

    return len(errors) == 0, errors

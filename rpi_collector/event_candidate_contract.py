"""Contract helpers for /event/candidate.

/event/candidate is created by the RPi preprocessing/synchronization module
after PIR/ToF raw samples and CSI features are fused. The final SRS contract
uses a nested sensorSummary.csi object instead of csiChangeScore/csiPacketCount.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from enums import CSI_STATUS, RISK_LEVELS


REQUIRED_TOP_LEVEL_FIELDS = {
    "type",
    "eventId",
    "timestamp",
    "deviceId",
    "roomId",
    "window",
    "sensorSummary",
    "localScore",
    "localRiskLevel",
    "candidateReason",
}

REQUIRED_WINDOW_FIELDS = {"startMonotonicNs", "endMonotonicNs", "durationMs"}
REQUIRED_SENSOR_SUMMARY_FIELDS = {
    "pirMotion",
    "pirLastMotionMs",
    "tofDistanceMm",
    "tofChangeMm",
    "tofStableMs",
    "csi",
}


def now_iso_millis() -> str:
    """Return local ISO-8601 timestamp with millisecond precision."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_window(window: Any, errors: List[str]) -> None:
    if not isinstance(window, dict):
        errors.append("window must be an object")
        return

    missing = sorted(REQUIRED_WINDOW_FIELDS - window.keys())
    if missing:
        errors.append(f"missing window fields: {missing}")

    for field_name in REQUIRED_WINDOW_FIELDS:
        value = window.get(field_name)
        if field_name in window:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"window.{field_name} must be non-negative integer")

    if isinstance(window.get("startMonotonicNs"), int) and isinstance(window.get("endMonotonicNs"), int):
        if window["endMonotonicNs"] < window["startMonotonicNs"]:
            errors.append("window.endMonotonicNs must be greater than or equal to startMonotonicNs")


def _validate_csi(csi: Any, errors: List[str]) -> None:
    if not isinstance(csi, dict):
        errors.append("sensorSummary.csi must be an object")
        return

    status = csi.get("status")
    if status not in CSI_STATUS:
        errors.append(f"sensorSummary.csi.status must be one of {sorted(CSI_STATUS)}")
        return

    if status == "AVAILABLE":
        if "changeScore" not in csi:
            errors.append("sensorSummary.csi.changeScore is required when status=AVAILABLE")
        elif not _is_number(csi["changeScore"]) or not 0.0 <= float(csi["changeScore"]) <= 1.0:
            errors.append("sensorSummary.csi.changeScore must be number between 0.0 and 1.0")

        if "packetCount" not in csi:
            errors.append("sensorSummary.csi.packetCount is required when status=AVAILABLE")
        elif not isinstance(csi["packetCount"], int) or isinstance(csi["packetCount"], bool) or csi["packetCount"] < 0:
            errors.append("sensorSummary.csi.packetCount must be non-negative integer")
    else:
        reason = csi.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append("sensorSummary.csi.reason is required when status is not AVAILABLE")


def validate_event_candidate(candidate: Dict[str, Any]) -> List[str]:
    """Return validation error messages. Empty list means publishable."""
    errors: List[str] = []

    missing_top = sorted(REQUIRED_TOP_LEVEL_FIELDS - candidate.keys())
    if missing_top:
        errors.append(f"missing top-level fields: {missing_top}")

    if candidate.get("type") != "event.candidate":
        errors.append("type must be 'event.candidate'")

    for field_name in ("eventId", "timestamp", "deviceId", "roomId"):
        if field_name in candidate and not isinstance(candidate[field_name], str):
            errors.append(f"{field_name} must be string")

    _validate_window(candidate.get("window"), errors)

    local_score = candidate.get("localScore")
    if "localScore" in candidate:
        if not _is_number(local_score) or not 0.0 <= float(local_score) <= 1.0:
            errors.append("localScore must be number between 0.0 and 1.0")

    if candidate.get("localRiskLevel") not in RISK_LEVELS:
        errors.append(f"localRiskLevel must be one of {sorted(RISK_LEVELS)}")

    candidate_reason = candidate.get("candidateReason")
    if not isinstance(candidate_reason, list) or not all(isinstance(item, str) for item in candidate_reason):
        errors.append("candidateReason must be a string array")

    sensor_summary = candidate.get("sensorSummary")
    if not isinstance(sensor_summary, dict):
        errors.append("sensorSummary must be an object")
        return errors

    missing_sensor = sorted(REQUIRED_SENSOR_SUMMARY_FIELDS - sensor_summary.keys())
    if missing_sensor:
        errors.append(f"missing sensorSummary fields: {missing_sensor}")

    if "pirMotion" in sensor_summary and not isinstance(sensor_summary["pirMotion"], bool):
        errors.append("sensorSummary.pirMotion must be boolean")

    for non_negative_int_field in ("pirLastMotionMs", "tofDistanceMm", "tofStableMs"):
        value = sensor_summary.get(non_negative_int_field)
        if non_negative_int_field in sensor_summary:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"sensorSummary.{non_negative_int_field} must be non-negative integer")

    tof_change = sensor_summary.get("tofChangeMm")
    if "tofChangeMm" in sensor_summary:
        if not isinstance(tof_change, int) or isinstance(tof_change, bool):
            errors.append("sensorSummary.tofChangeMm must be integer")

    _validate_csi(sensor_summary.get("csi"), errors)

    return errors


def build_sample_candidate(device_id: str, room_id: str) -> Dict[str, Any]:
    """Build a sample candidate for MQTT integration testing only."""
    start_ns = 123456789000
    end_ns = 124456789000
    return {
        "type": "event.candidate",
        "eventId": "EVT-TEST-001",
        "timestamp": now_iso_millis(),
        "deviceId": device_id,
        "roomId": room_id,
        "window": {
            "startMonotonicNs": start_ns,
            "endMonotonicNs": end_ns,
            "durationMs": 1000,
        },
        "sensorSummary": {
            "pirMotion": False,
            "pirLastMotionMs": 2400,
            "tofDistanceMm": 1820,
            "tofChangeMm": 680,
            "tofStableMs": 2100,
            "csi": {
                "status": "AVAILABLE",
                "changeScore": 0.82,
                "packetCount": 57,
            },
        },
        "localScore": 0.86,
        "localRiskLevel": "HIGH",
        "candidateReason": [
            "CSI 급격 변화",
            "ToF 거리 급변",
            "움직임 정지 지속",
        ],
    }

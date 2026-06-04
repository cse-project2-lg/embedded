"""Contract helpers for /csi/raw.

/csi/raw is an internal raw MQTT topic created by the Raspberry Pi CSI collector.
It carries Nexmon CSI UDP payload as base64 and RPi receive timestamps.

This module intentionally does not parse CSI amplitude/phase. Feature extraction,
PIR/ToF synchronization, and /event/candidate generation are owned by the
preprocessing/synchronization module.
"""

from __future__ import annotations

import base64
from typing import Any, Dict, List

REQUIRED_TOP_LEVEL_FIELDS = {
    "type",
    "source",
    "deviceId",
    "seq",
    "receivedAt",
    "receivedMonotonicNs",
    "interface",
    "udpPort",
    "payloadLen",
    "payloadBase64",
    "payloadPrefixHex",
}


def validate_csi_raw(payload: Dict[str, Any]) -> List[str]:
    """Return validation error messages. Empty list means the payload is usable."""
    errors: List[str] = []

    missing_top = sorted(REQUIRED_TOP_LEVEL_FIELDS - payload.keys())
    if missing_top:
        errors.append(f"missing top-level fields: {missing_top}")

    if payload.get("type") != "csi.raw":
        errors.append("type must be 'csi.raw'")

    if "seq" in payload and (not isinstance(payload["seq"], int) or payload["seq"] < 0):
        errors.append("seq must be a non-negative integer")

    if "receivedMonotonicNs" in payload and (
        not isinstance(payload["receivedMonotonicNs"], int) or payload["receivedMonotonicNs"] < 0
    ):
        errors.append("receivedMonotonicNs must be a non-negative integer")

    if "udpPort" in payload and (not isinstance(payload["udpPort"], int) or payload["udpPort"] <= 0):
        errors.append("udpPort must be a positive integer")

    if "payloadLen" in payload and (not isinstance(payload["payloadLen"], int) or payload["payloadLen"] <= 0):
        errors.append("payloadLen must be a positive integer")

    payload_base64 = payload.get("payloadBase64")
    payload_len = payload.get("payloadLen")
    if "payloadBase64" in payload and not isinstance(payload_base64, str):
        errors.append("payloadBase64 must be a string")
    elif isinstance(payload_base64, str):
        try:
            decoded = base64.b64decode(payload_base64, validate=True)
            if isinstance(payload_len, int) and payload_len > 0 and len(decoded) != payload_len:
                errors.append("payloadLen does not match decoded payloadBase64 length")
        except Exception:
            errors.append("payloadBase64 must be valid base64")

    payload_prefix_hex = payload.get("payloadPrefixHex")
    if "payloadPrefixHex" in payload and not isinstance(payload_prefix_hex, str):
        errors.append("payloadPrefixHex must be a string")
    elif isinstance(payload_prefix_hex, str):
        try:
            bytes.fromhex(payload_prefix_hex)
        except ValueError:
            errors.append("payloadPrefixHex must be valid hex")

    return errors

import logging
from typing import Any

from influxdb_client import Point, WritePrecision

from app.time_utils import parse_iso_datetime


logger = logging.getLogger(__name__)


def _require_non_empty_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value


def _safe_int(value: Any, default: int = 0, required: bool = False) -> int:
    try:
        if value is None:
            if required:
                raise ValueError("Required integer field is None")
            logger.warning("_safe_int received None, using default=%s", default)
            return default
        return int(value)
    except (TypeError, ValueError) as e:
        if required:
            raise ValueError(f"Failed to convert required field to int: {value}") from e
        logger.warning("_safe_int conversion failed for value=%s, using default=%s", value, default)
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False

    if value is None:
        return default

    return bool(value)


def sensor_raw_to_point(data: dict[str, Any]) -> Point:
    sensors = data.get("sensors", {})
    transport = data.get("transport", {})

    timestamp = parse_iso_datetime(data.get("mqttReceivedAt"))

    tof_error = sensors.get("tofError")
    tof_error_text = "" if tof_error is None else str(tof_error)

    return (
        Point("sensor_raw")
        .tag("device_id", _require_non_empty_str(data, "deviceId"))
        .tag("source", _require_non_empty_str(data, "source"))
        .field("seq", _safe_int(data.get("seq"), required=True))
        .field("sample_interval_ms", _safe_int(data.get("sampleIntervalMs"), 100, required=True))
        .field("pir_motion", _safe_bool(sensors.get("pirMotion")))
        .field("pir_value", _safe_int(sensors.get("pirValue")))
        .field("tof_distance_mm", _safe_int(sensors.get("tofDistanceMm")))
        .field("tof_valid", _safe_bool(sensors.get("tofValid"), False))
        .field("tof_timeout", _safe_bool(sensors.get("tofTimeout")))
        .field("tof_error", tof_error_text)
        .field("wifi_rssi_dbm", _safe_int(transport.get("wifiRssiDbm")))
        .field("ping_ok", _safe_bool(transport.get("pingOk"), False))
        .field("received_monotonic_ns", _safe_int(data.get("mqttReceivedMonotonicNs"), required=True))
        .time(timestamp, WritePrecision.NS)
    )


def csi_raw_to_point(data: dict[str, Any]) -> Point:
    timestamp = parse_iso_datetime(data.get("receivedAt"))

    return (
        Point("csi_raw")
        .tag("device_id", _require_non_empty_str(data, "deviceId"))
        .tag("source", _require_non_empty_str(data, "source"))
        .tag("interface", _require_non_empty_str(data, "interface"))
        .field("packet_id", str(data.get("packetId") or ""))
        .field("collector_session_id", str(data.get("collectorSessionId") or ""))
        .field("seq", _safe_int(data.get("seq"), required=True))
        .field("received_monotonic_ns", _safe_int(data.get("receivedMonotonicNs"), required=True))
        .field("udp_port", _safe_int(data.get("udpPort"), 5500))
        .field("payload_len", _safe_int(data.get("payloadLen"), required=True))
        .field("payload_prefix_hex", str(data.get("payloadPrefixHex") or ""))
        .field("raw_log_file", str(data.get("rawLogFile") or ""))
        .time(timestamp, WritePrecision.NS)
    )
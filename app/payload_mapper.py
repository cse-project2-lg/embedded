import logging
from typing import Any

from influxdb_client import Point, WritePrecision

from app.time_utils import parse_iso_datetime


logger = logging.getLogger(__name__)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
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
    mqtt_meta = data.get("_mqtt", {})
    sensors = data.get("sensors", {})
    transport = data.get("transport", {})

    timestamp = parse_iso_datetime(mqtt_meta.get("receivedAt"))

    tof_error = sensors.get("tofError")
    tof_error_text = "" if tof_error is None else str(tof_error)

    return (
        Point("sensor_raw")
        .tag("device_id", str(data.get("deviceId", "UNKNOWN_DEV")))
        .tag("source", str(data.get("source", "UNKNOWN_SRC")))
        .field("seq", _safe_int(data.get("seq")))
        .field("sample_interval_ms", _safe_int(data.get("sampleIntervalMs"), 100))
        .field("pir_motion", _safe_bool(sensors.get("pirMotion")))
        .field("pir_value", float(_safe_int(sensors.get("pirValue"))))        .field("tof_distance_mm", _safe_int(sensors.get("tofDistanceMm")))
        .field("tof_valid", _safe_bool(sensors.get("tofValid"), True))
        .field("tof_timeout", _safe_bool(sensors.get("tofTimeout")))
        .field("tof_error", tof_error_text)
        .field("wifi_rssi_dbm", _safe_int(transport.get("wifiRssiDbm")))
        .field("ping_ok", _safe_bool(transport.get("pingOk"), True))
        .field("received_monotonic_ns", _safe_int(mqtt_meta.get("receivedMonotonicNs")))
        .time(timestamp, WritePrecision.NS)
    )


def csi_raw_to_point(data: dict[str, Any]) -> Point:
    timestamp = parse_iso_datetime(data.get("receivedAt"))

    return (
        Point("csi_raw")
        .tag("device_id", str(data.get("deviceId", "UNKNOWN_DEV")))
        .tag("source", str(data.get("source", "UNKNOWN_SRC")))
        .tag("interface", str(data.get("interface", "wlan0")))
        .field("packet_id", str(data.get("packetId", "")))
        .field("collector_session_id", str(data.get("collectorSessionId", "")))
        .field("seq", _safe_int(data.get("seq")))
        .field("received_monotonic_ns", _safe_int(data.get("receivedMonotonicNs")))
        .field("udp_port", _safe_int(data.get("udpPort"), 5500))
        .field("payload_len", _safe_int(data.get("payloadLen")))
        .field("payload_prefix_hex", str(data.get("payloadPrefixHex", "")))
        .field("raw_log_file", str(data.get("rawLogFile", "")))
        .time(timestamp, WritePrecision.NS)
    )
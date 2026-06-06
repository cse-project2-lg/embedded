"""Build lightweight timestamp-based synced frames from /sensor/raw and /csi/raw.

This module is the bridge between raw collection and the preprocessing team's
5-second windowing code.

Input topics:
- /sensor/raw: ESP32 PIR/ToF sample. ESP32 has no wall-clock timestamp, so the
  Raspberry Pi MQTT receive monotonic timestamp is used as the frame timestamp.
- /csi/raw: Nexmon CSI UDP payload wrapped by csi_raw_collector.py.

Output:
- JSONL: synced_frame_YYYYMMDD.jsonl
- MQTT: /preprocess/synced_frame by default

Important boundary:
- This module does timestamp alignment only.
- It does not create 5-second windows.
- It does not extract CSI amplitude/phase features.
- It does not publish /event/candidate.

Frame rule:
- One sensor sample becomes one synced.frame.
- CSI packets whose RPi receive monotonic timestamp falls between the previous
  sensor timestamp and the current sensor timestamp are referenced by that frame.
- For the first sensor sample, SYNC_CSI_LOOKBACK_MS is used as the start range.

Payload contract:
- raw.sensorRaw preserves the original /sensor/raw payload shape.
- raw.csiRawRefs is a lightweight reference list. It does NOT include
  payloadBase64.
- Full CSI payloads remain in CSI_RAW_LOG_DIR/csi_raw_YYYYMMDD.jsonl and can be
  retrieved later by packetId/rawLogFile.
"""

from __future__ import annotations

import argparse
import json
import signal
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Deque, Dict, List, Optional

from config import (
    MQTT_RAW_LOG_DIR,
    MQTT_HOST,
    MQTT_PORT,
    SYNC_CSI_LOOKBACK_MS,
    SYNC_CSI_RETENTION_MS,
    SYNC_FRAME_EMIT_DELAY_MS,
    SYNC_FRAME_INCLUDE_CSI_PAYLOAD,
    SYNC_FRAME_LOG_DIR,
    SYNC_FRAME_MAX_CSI_PACKETS,
    SYNC_FRAME_PUBLISH_ENABLED,
    SYNC_FRAME_QOS,
    TOPIC_CSI_RAW,
    TOPIC_SENSOR_RAW,
    TOPIC_SYNCED_FRAME,
)
from mqtt_client import create_mqtt_client, parse_json_message, publish_json
from raw_mqtt_subscriber import append_jsonl as append_raw_jsonl
from raw_mqtt_subscriber import handle_raw_message

Ns = int
MQTT_META_KEYS = {"mqttTopic", "mqttReceivedAt", "mqttReceivedMonotonicNs"}


def now_iso_ms() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def ns_from_ms(value_ms: int) -> Ns:
    return int(value_ms) * 1_000_000


def log_path(kind: str) -> Path:
    date_key = datetime.now().strftime("%Y%m%d")
    return Path(SYNC_FRAME_LOG_DIR).expanduser() / f"{kind}_{date_key}.jsonl"


def append_jsonl(kind: str, payload: Dict[str, Any]) -> None:
    path = log_path(kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False) + "\n")


def csi_received_ns(csi_record: Dict[str, Any]) -> Optional[Ns]:
    value = csi_record.get("receivedMonotonicNs")
    if isinstance(value, int):
        return value
    return None


def sensor_received_ns(sensor_record: Dict[str, Any]) -> Optional[Ns]:
    value = sensor_record.get("mqttReceivedMonotonicNs")
    if isinstance(value, int):
        return value
    return None


def preserved_raw_message(enriched_record: Dict[str, Any]) -> Dict[str, Any]:
    """Return the original raw JSON shape without local MQTT metadata."""
    return {k: v for k, v in enriched_record.items() if k not in MQTT_META_KEYS}


def csi_raw_ref(enriched_record: Dict[str, Any]) -> Dict[str, Any]:
    """Return the lightweight reference needed to find the full CSI raw row later.

    packetId is the primary key. rawLogFile tells which CSI raw JSONL file to
    scan. seq and timestamps are included for debugging and fallback search.
    payloadPrefixHex is intentionally short and is not a replacement for the
    full payloadBase64.
    """
    return {
        "packetId": enriched_record.get("packetId"),
        "seq": enriched_record.get("seq"),
        "receivedAt": enriched_record.get("receivedAt"),
        "receivedMonotonicNs": enriched_record.get("receivedMonotonicNs"),
        "payloadLen": enriched_record.get("payloadLen"),
        "payloadPrefixHex": enriched_record.get("payloadPrefixHex"),
        "rawLogFile": enriched_record.get("rawLogFile"),
    }


class SyncedFrameBuilder:
    def __init__(
        self,
        mqtt_client,
        publish_enabled: bool,
        output_topic: str,
        emit_delay_ms: int,
        csi_lookback_ms: int,
        csi_retention_ms: int,
        include_csi_payload: bool,
        max_csi_packets: int,
    ) -> None:
        self.mqtt_client = mqtt_client
        self.publish_enabled = publish_enabled
        self.output_topic = output_topic
        self.emit_delay_ns = ns_from_ms(emit_delay_ms)
        self.csi_lookback_ns = ns_from_ms(csi_lookback_ms)
        self.csi_retention_ns = ns_from_ms(csi_retention_ms)
        self.include_csi_payload = include_csi_payload
        self.max_csi_packets = max_csi_packets

        self.lock = Lock()
        self.csi_buffer: Deque[Dict[str, Any]] = deque()
        self.sensor_buffer: Deque[Dict[str, Any]] = deque()
        self.previous_sensor_ns: Optional[Ns] = None
        self.frame_seq = 1

    def ingest(self, enriched: Dict[str, Any]) -> None:
        topic = enriched.get("mqttTopic")
        with self.lock:
            if topic == TOPIC_CSI_RAW:
                if csi_received_ns(enriched) is not None:
                    self.csi_buffer.append(enriched)
            elif topic == TOPIC_SENSOR_RAW:
                if sensor_received_ns(enriched) is not None:
                    self.sensor_buffer.append(enriched)

    def prune_old_csi(self, keep_after_ns: Ns) -> None:
        while self.csi_buffer:
            csi_ns = csi_received_ns(self.csi_buffer[0])
            if csi_ns is None or csi_ns < keep_after_ns:
                self.csi_buffer.popleft()
            else:
                break

    def emit_ready_frames(self) -> int:
        emitted = 0
        now_ns = time.monotonic_ns()

        ready_sensors: List[Dict[str, Any]] = []
        with self.lock:
            while self.sensor_buffer:
                sensor_ns = sensor_received_ns(self.sensor_buffer[0])
                if sensor_ns is None:
                    self.sensor_buffer.popleft()
                    continue
                if sensor_ns + self.emit_delay_ns > now_ns:
                    break
                ready_sensors.append(self.sensor_buffer.popleft())

        for sensor_record in ready_sensors:
            frame = self.build_frame(sensor_record)
            append_jsonl("synced_frame", frame)
            self.publish_frame(frame)
            emitted += 1

            summary = frame.get("summary", {})
            packet_count = summary.get("csiPacketCount", 0)
            if packet_count == 0:
                print(f"SYNCED FRAME frameId={frame['frameId']} csiPackets=0")
            elif self.frame_seq <= 5 or self.frame_seq % 20 == 0:
                print(
                    f"SYNCED FRAME frameId={frame['frameId']} "
                    f"csiPackets={packet_count} tof={summary.get('tofDistanceMm')} "
                    f"pir={summary.get('pirMotion')}"
                )

        if ready_sensors:
            oldest_keep_ns = time.monotonic_ns() - self.csi_retention_ns
            with self.lock:
                self.prune_old_csi(oldest_keep_ns)

        return emitted

    def build_frame(self, sensor_record: Dict[str, Any]) -> Dict[str, Any]:
        sensor_ns = sensor_received_ns(sensor_record)
        if sensor_ns is None:
            raise ValueError("sensor_record has no mqttReceivedMonotonicNs")

        if self.previous_sensor_ns is None:
            range_start_ns = sensor_ns - self.csi_lookback_ns
        else:
            range_start_ns = self.previous_sensor_ns
        range_end_ns = sensor_ns

        with self.lock:
            matched_csi = [
                csi
                for csi in self.csi_buffer
                if (csi_received_ns(csi) is not None and range_start_ns < csi_received_ns(csi) <= range_end_ns)
            ]

        if self.max_csi_packets > 0 and len(matched_csi) > self.max_csi_packets:
            matched_csi = matched_csi[-self.max_csi_packets :]

        sensor_raw = preserved_raw_message(sensor_record)
        csi_refs = [csi_raw_ref(item) for item in matched_csi]

        raw_payload: Dict[str, Any] = {
            "sensorRaw": sensor_raw,
            "csiRawRefs": csi_refs,
        }
        # Keep synced.frame lightweight. Full CSI payloads remain in csi_raw JSONL logs.
        # The include_csi_payload flag is accepted for backward CLI compatibility,
        # but the final handoff contract intentionally uses csiRawRefs only.

        frame = {
            "type": "synced.frame",
            "source": "rpi_synced_frame_builder",
            "frameId": f"FRAME-{datetime.now().strftime('%Y%m%d')}-{self.frame_seq:06d}",
            "timestamp": sensor_record.get("mqttReceivedAt") or now_iso_ms(),
            "frameMonotonicNs": sensor_ns,
            "raw": raw_payload,
            "summary": self.build_summary(sensor_raw, csi_refs),
        }

        self.previous_sensor_ns = sensor_ns
        self.frame_seq += 1
        return frame

    def build_summary(self, sensor_raw: Dict[str, Any], csi_refs: List[Dict[str, Any]]) -> Dict[str, Any]:
        sensors = sensor_raw.get("sensors", {}) if isinstance(sensor_raw.get("sensors"), dict) else {}
        transport = sensor_raw.get("transport", {}) if isinstance(sensor_raw.get("transport"), dict) else {}
        return {
            "csiPacketCount": len(csi_refs),
            "csiFirstSeq": csi_refs[0].get("seq") if csi_refs else None,
            "csiLastSeq": csi_refs[-1].get("seq") if csi_refs else None,
            "tofDistanceMm": sensors.get("tofDistanceMm"),
            "pirMotion": sensors.get("pirMotion"),
            "pingOk": transport.get("pingOk"),
        }

    def publish_frame(self, frame: Dict[str, Any]) -> None:
        if not self.publish_enabled or self.mqtt_client is None:
            return
        try:
            publish_json(self.mqtt_client, self.output_topic, frame, qos=SYNC_FRAME_QOS, wait=False)
        except Exception as exc:
            error_record = {
                "type": "synced.frame.publish_error",
                "timestamp": now_iso_ms(),
                "frameId": frame.get("frameId"),
                "topic": self.output_topic,
                "error": str(exc),
            }
            append_jsonl("synced_frame_error", error_record)
            print(f"SYNCED FRAME publish error frameId={frame.get('frameId')}: {exc}")


def build_on_message(builder: SyncedFrameBuilder):
    def _on_message(mqtt_client, userdata, msg) -> None:
        try:
            payload = parse_json_message(msg)
            enriched = handle_raw_message(msg.topic, payload, on_valid_message=builder.ingest)
            if enriched is None:
                return
        except Exception as exc:
            error_record = {
                "type": "synced.frame.receive_error",
                "mqttTopic": getattr(msg, "topic", "unknown"),
                "mqttReceivedAt": now_iso_ms(),
                "error": str(exc),
            }
            append_jsonl("synced_frame_error", error_record)
            append_raw_jsonl("receive_error", error_record)
            print(f"synced_frame_builder 처리 오류: {exc}")

    return _on_message


def run_builder(args: argparse.Namespace) -> None:
    mqtt_client = create_mqtt_client("synced-frame-builder")
    mqtt_client.loop_start()

    include_csi_payload = args.include_csi_payload or (
        SYNC_FRAME_INCLUDE_CSI_PAYLOAD and not args.no_csi_payload
    )

    builder = SyncedFrameBuilder(
        mqtt_client=mqtt_client,
        publish_enabled=not args.no_publish and SYNC_FRAME_PUBLISH_ENABLED,
        output_topic=args.topic,
        emit_delay_ms=args.emit_delay_ms,
        csi_lookback_ms=args.csi_lookback_ms,
        csi_retention_ms=args.csi_retention_ms,
        include_csi_payload=include_csi_payload,
        max_csi_packets=args.max_csi_packets,
    )

    mqtt_client.on_message = build_on_message(builder)
    mqtt_client.subscribe(TOPIC_SENSOR_RAW, qos=1)
    mqtt_client.subscribe(TOPIC_CSI_RAW, qos=1)

    running = True

    def _stop(_signum, _frame) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    print("synced_frame_builder 실행 중...")
    print(f"MQTT broker: {MQTT_HOST}:{MQTT_PORT}")
    print(f"subscribe: {TOPIC_SENSOR_RAW}")
    print(f"subscribe: {TOPIC_CSI_RAW}")
    print(f"publish: {builder.publish_enabled}, topic: {args.topic}, qos: {SYNC_FRAME_QOS}")
    print(f"raw mqtt log dir: {MQTT_RAW_LOG_DIR}")
    print(f"synced frame log dir: {SYNC_FRAME_LOG_DIR}")
    print("include CSI payload in synced.frame: False (final contract uses csiRawRefs only)")
    print("frame rule: sensor raw 1개마다 직전 sensor timestamp 이후부터 현재 sensor timestamp까지의 CSI raw ref를 붙임")
    print("payload contract: sensorRaw는 원본 유지, csiRawRefs는 packetId 기반 참조만 보냄")
    print("주의: 5초 window 생성과 feature 추출은 이 파일에서 수행하지 않음.")

    try:
        while running:
            builder.emit_ready_frames()
            time.sleep(0.02)
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        print("synced_frame_builder 종료")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build timestamp-based synced.frame from /sensor/raw and /csi/raw")
    parser.add_argument("--topic", default=TOPIC_SYNCED_FRAME, help="MQTT output topic for synced.frame")
    parser.add_argument("--no-publish", action="store_true", help="Write JSONL only; do not publish synced.frame MQTT")
    parser.add_argument(
        "--include-csi-payload",
        action="store_true",
        help="Also include full raw.csiRawPackets with payloadBase64. Default is refs only.",
    )
    parser.add_argument(
        "--no-csi-payload",
        action="store_true",
        help="Compatibility option. Default already excludes CSI payload unless env enables it.",
    )
    parser.add_argument("--emit-delay-ms", type=int, default=SYNC_FRAME_EMIT_DELAY_MS)
    parser.add_argument("--csi-lookback-ms", type=int, default=SYNC_CSI_LOOKBACK_MS)
    parser.add_argument("--csi-retention-ms", type=int, default=SYNC_CSI_RETENTION_MS)
    parser.add_argument("--max-csi-packets", type=int, default=SYNC_FRAME_MAX_CSI_PACKETS)
    return parser.parse_args()


def main() -> None:
    run_builder(parse_args())


if __name__ == "__main__":
    main()

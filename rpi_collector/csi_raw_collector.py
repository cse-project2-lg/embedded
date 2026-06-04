"""Collect Nexmon CSI UDP packets and publish raw payloads to MQTT.

Responsibility boundary:
- This file receives Nexmon CSI UDP packets on RPi wlan0-side CSI setup.
- It wraps each raw UDP payload into a JSON message and publishes /csi/raw.
- It also writes JSONL logs for debugging/replay.
- It does NOT parse amplitude/phase, synchronize PIR/ToF, extract features, or
  create /event/candidate. Those belong to the preprocessing team.

Expected upstream setup:
    Nexmon CSI configured with makecsiparams, e.g. channel 1/20 MHz.
    tcpdump -ni wlan0 udp port 5500 should show packets before this script is useful.
"""

from __future__ import annotations

import argparse
import base64
import json
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

from config import (
    CSI_INTERFACE,
    CSI_MQTT_PUBLISH_ENABLED,
    CSI_MQTT_QOS,
    CSI_RAW_LOG_DIR,
    CSI_UDP_BIND_HOST,
    CSI_UDP_PORT,
    DEVICE_ID,
    TOPIC_CSI_RAW,
)
from mqtt_client import create_mqtt_client, publish_json


def now_iso_ms() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def today_log_path() -> Path:
    date_key = datetime.now().strftime("%Y%m%d")
    return Path(CSI_RAW_LOG_DIR) / f"csi_raw_{date_key}.jsonl"


def append_jsonl(payload: Dict[str, Any]) -> None:
    path = today_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False) + "\n")


def build_csi_raw_message(seq: int, data: bytes, remote_addr: Tuple[str, int], udp_port: int) -> Dict[str, Any]:
    return {
        "type": "csi.raw",
        "source": "rpi_nexmon_csi",
        "deviceId": DEVICE_ID,
        "seq": seq,
        "receivedAt": now_iso_ms(),
        "receivedMonotonicNs": time.monotonic_ns(),
        "interface": CSI_INTERFACE,
        "udpPort": udp_port,
        "remoteAddr": f"{remote_addr[0]}:{remote_addr[1]}",
        "payloadLen": len(data),
        "payloadBase64": base64.b64encode(data).decode("ascii"),
        "payloadPrefixHex": data[:32].hex(),
    }


def open_udp_socket(host: str, port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind((host, port))
    return sock


def run_collector(bind_host: str, udp_port: int, mqtt_enabled: bool, topic: str) -> None:
    mqtt_client = None
    sock = None
    if mqtt_enabled:
        mqtt_client = create_mqtt_client("csi-raw-collector")
        mqtt_client.loop_start()

    try:
        sock = open_udp_socket(bind_host, udp_port)
        print("csi_raw_collector 실행 중...")
        print(f"UDP listen: {bind_host}:{udp_port}")
        print(f"MQTT publish: {mqtt_enabled}, topic: {topic}, qos: {CSI_MQTT_QOS}")
        print(f"JSONL log dir: {CSI_RAW_LOG_DIR}")
        print("주의: 이 코드는 raw 수집/통신까지만 담당하고 feature 추출은 하지 않음.")

        seq = 0
        while True:
            data, remote_addr = sock.recvfrom(65535)
            record = build_csi_raw_message(seq, data, remote_addr, udp_port)
            append_jsonl(record)

            if mqtt_client is not None:
                try:
                    publish_json(mqtt_client, topic, record, qos=CSI_MQTT_QOS, wait=False)
                except Exception as exc:
                    error_record = {
                        "type": "csi.raw.publish_error",
                        "seq": seq,
                        "timestamp": now_iso_ms(),
                        "topic": topic,
                        "error": str(exc),
                    }
                    append_jsonl(error_record)
                    print(f"CSI RAW publish error seq={seq}: {exc}")

            if seq < 5 or seq % 50 == 0:
                print(
                    f"CSI RAW seq={seq} len={record['payloadLen']} "
                    f"prefix={record['payloadPrefixHex']}"
                )

            seq += 1
    except KeyboardInterrupt:
        print("csi_raw_collector 종료 요청 수신")
    finally:
        if sock is not None:
            sock.close()
        if mqtt_client is not None:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nexmon CSI UDP 5500 → /csi/raw MQTT collector")
    parser.add_argument("--host", default=CSI_UDP_BIND_HOST, help="UDP bind host, default 0.0.0.0")
    parser.add_argument("--port", type=int, default=CSI_UDP_PORT, help="UDP port, default 5500")
    parser.add_argument("--topic", default=TOPIC_CSI_RAW, help="MQTT topic, default /csi/raw")
    parser.add_argument("--no-mqtt", action="store_true", help="Only write JSONL; do not publish MQTT")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mqtt_enabled = CSI_MQTT_PUBLISH_ENABLED and not args.no_mqtt
    run_collector(args.host, args.port, mqtt_enabled, args.topic)


if __name__ == "__main__":
    main()

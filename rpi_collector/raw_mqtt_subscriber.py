"""Subscribe raw MQTT input topics and hand off usable messages.

This is the communication handoff layer for the preprocessing team.
It subscribes:
- /sensor/raw from ESP32
- /csi/raw from RPi csi_raw_collector.py

It validates and logs raw messages. It intentionally does not synchronize,
extract features, or publish /event/candidate.

Integration point:
    from raw_mqtt_subscriber import run_subscriber
    run_subscriber(on_valid_message=preprocessing_queue.put)
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from typing import Any, Callable, Dict, List, Optional

from config import MQTT_RAW_LOG_DIR, TOPIC_CSI_RAW, TOPIC_SENSOR_RAW
from csi_raw_contract import validate_csi_raw
from mqtt_client import create_mqtt_client, parse_json_message
from raw_message_contract import validate_sensor_raw

RawMessageCallback = Callable[[Dict[str, Any]], None]

# Optional in-process queue for integration tests or for a preprocessing module
# that imports this subscriber instead of running it as a separate process.
PREPROCESSING_HANDOFF_QUEUE: "Queue[Dict[str, Any]]" = Queue()


def now_iso_ms() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def log_path(kind: str) -> Path:
    date_key = datetime.now().strftime("%Y%m%d")
    return Path(MQTT_RAW_LOG_DIR) / f"{kind}_{date_key}.jsonl"


def append_jsonl(kind: str, payload: Dict[str, Any]) -> None:
    path = log_path(kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False) + "\n")


def enrich_mqtt_receive(topic: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(payload)
    enriched["mqttTopic"] = topic
    enriched["mqttReceivedAt"] = now_iso_ms()
    enriched["mqttReceivedMonotonicNs"] = time.monotonic_ns()
    return enriched


def validate_by_topic(topic: str, payload: Dict[str, Any]) -> List[str]:
    if topic == TOPIC_SENSOR_RAW:
        return validate_sensor_raw(payload)
    if topic == TOPIC_CSI_RAW:
        return validate_csi_raw(payload)
    return [f"unsupported topic: {topic}"]


def log_kind_by_topic(topic: str) -> str:
    if topic == TOPIC_SENSOR_RAW:
        return "sensor_raw"
    if topic == TOPIC_CSI_RAW:
        return "csi_raw"
    return "unknown_raw"


def enqueue_for_preprocessing(enriched: Dict[str, Any]) -> None:
    """Default handoff sink used by tests or same-process preprocessing.

    실제 전처리/동기화 로직은 여기서 수행하지 않음.
    전처리는 이 함수 대신 preprocessing_queue.put 같은 콜백을 넘기면 됨.
    """
    PREPROCESSING_HANDOFF_QUEUE.put(enriched)


def build_logging_handoff_callback() -> RawMessageCallback:
    """Return a callback that records every handoff for integration debugging."""

    def _callback(enriched: Dict[str, Any]) -> None:
        append_jsonl("preprocessing_handoff", enriched)
        enqueue_for_preprocessing(enriched)

    return _callback


def handle_raw_message(
    topic: str,
    payload: Dict[str, Any],
    on_valid_message: Optional[RawMessageCallback] = None,
) -> Optional[Dict[str, Any]]:
    errors = validate_by_topic(topic, payload)
    enriched = enrich_mqtt_receive(topic, payload)

    if errors:
        invalid_record = {
            "type": "mqtt.raw.invalid",
            "mqttTopic": topic,
            "mqttReceivedAt": enriched["mqttReceivedAt"],
            "mqttReceivedMonotonicNs": enriched["mqttReceivedMonotonicNs"],
            "errors": errors,
            "payload": payload,
        }
        append_jsonl("invalid_raw", invalid_record)
        print(f"INVALID {topic}: {errors}")
        return None

    kind = log_kind_by_topic(topic)
    append_jsonl(kind, enriched)

    if topic == TOPIC_SENSOR_RAW:
        print(
            f"SENSOR RAW OK seq={enriched.get('seq')} "
            f"pir={enriched.get('sensors', {}).get('pirMotion')} "
            f"tof={enriched.get('sensors', {}).get('tofDistanceMm')}"
        )
    elif topic == TOPIC_CSI_RAW:
        print(
            f"CSI RAW OK seq={enriched.get('seq')} "
            f"payloadLen={enriched.get('payloadLen')} "
            f"prefix={enriched.get('payloadPrefixHex')}"
        )

    if on_valid_message is not None:
        try:
            on_valid_message(enriched)
        except Exception as exc:
            error_record = {
                "type": "mqtt.raw.handoff_error",
                "mqttTopic": topic,
                "mqttReceivedAt": enriched["mqttReceivedAt"],
                "mqttReceivedMonotonicNs": enriched["mqttReceivedMonotonicNs"],
                "error": str(exc),
                "payload": enriched,
            }
            append_jsonl("handoff_error", error_record)
            print(f"HANDOFF ERROR {topic}: {exc}")
            return None

    return enriched


def on_message(mqtt_client, userdata, msg) -> None:
    try:
        payload = parse_json_message(msg)
        callback = None
        if isinstance(userdata, dict):
            callback = userdata.get("on_valid_message")
        handle_raw_message(msg.topic, payload, on_valid_message=callback)
    except Exception as exc:
        error_record = {
            "type": "mqtt.raw.receive_error",
            "mqttTopic": getattr(msg, "topic", "unknown"),
            "mqttReceivedAt": now_iso_ms(),
            "error": str(exc),
        }
        append_jsonl("receive_error", error_record)
        print(f"raw_mqtt_subscriber 처리 오류: {exc}")


def run_subscriber(on_valid_message: Optional[RawMessageCallback] = None) -> None:
    client = create_mqtt_client("raw-mqtt-subscriber")
    client.user_data_set({"on_valid_message": on_valid_message})
    client.on_message = on_message
    client.subscribe(TOPIC_SENSOR_RAW, qos=1)
    client.subscribe(TOPIC_CSI_RAW, qos=1)

    print("raw_mqtt_subscriber 실행 중...")
    print(f"subscribe: {TOPIC_SENSOR_RAW}")
    print(f"subscribe: {TOPIC_CSI_RAW}")
    print(f"raw mqtt log dir: {MQTT_RAW_LOG_DIR}")
    print("주의: 이 코드는 통신/검증/로그/전달까지만 담당하고 동기화/feature 추출은 하지 않음.")
    client.loop_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Subscribe /sensor/raw and /csi/raw, then hand off valid raw messages")
    parser.add_argument(
        "--handoff-log",
        action="store_true",
        help="Also write valid handoff messages to preprocessing_handoff_YYYYMMDD.jsonl",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    callback = build_logging_handoff_callback() if args.handoff_log else enqueue_for_preprocessing
    run_subscriber(on_valid_message=callback)


if __name__ == "__main__":
    main()

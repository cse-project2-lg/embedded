"""Subscribe ESP32 raw PIR/ToF samples from /sensor/raw.

This module only performs raw ingress + RPi receive timestamp attachment.
Data preprocessing, CSI synchronization, feature extraction, and candidate object
creation are intentionally excluded.

/event/candidate MQTT publish is handled separately by event_candidate_publisher.py
after the preprocessing/synchronization module creates the final candidate JSON.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from config import RAW_LOG_DIR, RAW_LOG_ENABLED, TOPIC_SENSOR_RAW
from mqtt_client import create_mqtt_client, parse_json_message
from raw_message_contract import validate_sensor_raw


def now_iso_ms() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def today_log_path() -> Path:
    date_key = datetime.now().strftime("%Y%m%d")
    return Path(RAW_LOG_DIR) / f"sensor_raw_{date_key}.jsonl"


def append_jsonl(payload: Dict[str, Any]) -> None:
    if not RAW_LOG_ENABLED:
        return

    path = today_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False) + "\n")


def add_rpi_receive_timestamp(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach the RPi-side receive time used as the common edge time base."""
    enriched = dict(payload)
    enriched["rpiReceivedAt"] = now_iso_ms()
    enriched["rpiReceivedMonotonicNs"] = time.monotonic_ns()
    return enriched


def handle_sensor_raw(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    errors = validate_sensor_raw(payload)
    if errors:
        error_record = {
            "type": "sensor.raw.invalid",
            "rpiReceivedAt": now_iso_ms(),
            "errors": errors,
            "payload": payload,
        }
        append_jsonl(error_record)
        print(f"INVALID {TOPIC_SENSOR_RAW}: {errors}")
        return None

    enriched = add_rpi_receive_timestamp(payload)
    append_jsonl(enriched)

    print(
        "RAW OK "
        f"seq={enriched.get('seq')} "
        f"pir={enriched['sensors'].get('pirMotion')} "
        f"tof={enriched['sensors'].get('tofDistanceMm')} "
        f"rpiReceivedAt={enriched.get('rpiReceivedAt')}"
    )

    # ------------------------------------------------------------------
    # TODO(전처리/동기화):
    # 1. enriched PIR/ToF raw sample을 rolling buffer 또는 내부 queue에 저장
    # 2. Nexmon CSI 수신 데이터와 RPi 시간 기준으로 동기화
    # 3. CSI/PIR/ToF 특징 추출
    # 4. 최종 candidate JSON을 만든 뒤, 아래 통신 담당 파일을 호출
    #
    # from event_candidate_publisher import publish_event_candidate
    # candidate = preprocessing_module.make_candidate(...)
    # publish_event_candidate(candidate)
    #
    # 주의: 이 파일은 /sensor/raw 수신 담당이다.
    # /event/candidate 발행은 event_candidate_publisher.py에서 담당한다.
    # ------------------------------------------------------------------

    return enriched


def on_message(mqtt_client, userdata, msg) -> None:
    try:
        payload = parse_json_message(msg)
        handle_sensor_raw(payload)
    except Exception as exc:
        error_record = {
            "type": "sensor.raw.receive_error",
            "rpiReceivedAt": now_iso_ms(),
            "error": str(exc),
        }
        append_jsonl(error_record)
        print(f"sensor_raw_subscriber 처리 오류: {exc}")


def main() -> None:
    client = create_mqtt_client("sensor-raw-subscriber")
    client.subscribe(TOPIC_SENSOR_RAW, qos=1)
    client.on_message = on_message

    print("sensor_raw_subscriber 실행 중...")
    print(f"subscribe: {TOPIC_SENSOR_RAW}")
    print(f"raw log enabled: {RAW_LOG_ENABLED}, dir: {RAW_LOG_DIR}")
    print("candidate publish module: rpi_collector/event_candidate_publisher.py")

    client.loop_forever()


if __name__ == "__main__":
    main()

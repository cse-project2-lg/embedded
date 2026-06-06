"""Publish final candidate events to /event/candidate.

담당 범위:
- 전처리/동기화 모듈이 만들어 준 candidate JSON을 받는다.
- 프로젝트 코드가 기대하는 JSON 구조인지 검증한다.
- MQTT topic /event/candidate 로 발행한다.

담당하지 않는 범위:
- PIR/ToF/CSI 시간 동기화
- CSI complex numpy array 파싱
- tofChangeMm, csiChangeScore, localScore 계산
- 낙상 후보 판단 로직

사용 예시:
    from event_candidate_publisher import publish_event_candidate

    candidate = preprocessing_team_module.make_candidate(...)
    publish_event_candidate(candidate)
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt

from config import DEVICE_ID, ROOM_ID, TOPIC_EVENT_CANDIDATE
from event_candidate_contract import build_sample_candidate, validate_event_candidate
from mqtt_client import create_mqtt_client, publish_json


class EventCandidatePublishError(ValueError):
    """Raised when a candidate event cannot be published."""


def publish_event_candidate(
    candidate: Dict[str, Any],
    mqtt_client: Optional[mqtt.Client] = None,
    qos: int = 1,
) -> None:
    """Validate and publish a candidate event JSON to /event/candidate.

    Args:
        candidate: Final event candidate JSON created by preprocessing/sync logic.
        mqtt_client: Existing MQTT client. If omitted, this function creates one.
        qos: MQTT QoS level. Default 1 for at-least-once delivery.

    Raises:
        EventCandidatePublishError: if the candidate does not match the project contract.
    """
    errors = validate_event_candidate(candidate)
    if errors:
        raise EventCandidatePublishError("invalid /event/candidate payload: " + "; ".join(errors))

    owns_client = mqtt_client is None
    client = mqtt_client or create_mqtt_client("event-candidate-publisher")

    publish_json(client, TOPIC_EVENT_CANDIDATE, candidate, qos=qos)

    if owns_client:
        # Give the MQTT client a short moment to flush the publish packet.
        time.sleep(0.2)
        client.disconnect()


def load_candidate_json(path: str) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fp:
        payload = json.load(fp)

    if not isinstance(payload, dict):
        raise EventCandidatePublishError("candidate file must contain one JSON object")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish /event/candidate MQTT message")
    parser.add_argument(
        "--file",
        help="Path to candidate JSON file created by preprocessing/sync module",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Publish built-in sample candidate for integration testing",
    )
    args = parser.parse_args()

    if args.file:
        candidate = load_candidate_json(args.file)
    else:
        # Default to sample so the MQTT path can be tested before preprocessing is ready.
        candidate = build_sample_candidate(DEVICE_ID, ROOM_ID)

    publish_event_candidate(candidate)
    print(f"{TOPIC_EVENT_CANDIDATE} 발행 완료: {candidate}")


if __name__ == "__main__":
    main()

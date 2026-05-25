"""MQTT-to-REST bridge for AI/RAG analysis.

Flow:
/event/candidate  --MQTT-->  analysis_bridge.py
analysis_bridge.py --REST--> AI/RAG server
AI/RAG response    --MQTT-->  /analysis/result

This module does not preprocess sensor data. The preprocessing/synchronization
module only needs to publish the final candidate event JSON to /event/candidate.
"""

from typing import Any, Dict

import requests

from config import (
    AI_ANALYZE_URL,
    REQUEST_TIMEOUT_SEC,
    TOPIC_ANALYSIS_RESULT,
    TOPIC_EVENT_CANDIDATE,
)
from mqtt_client import create_mqtt_client, parse_json_message, publish_json


client = create_mqtt_client("analysis-bridge")


def fallback_result(event: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return {
        "eventId": event.get("eventId"),
        "isFall": True,
        "confidence": 0.6,
        "riskLevel": "MEDIUM",
        "recommendedAction": "VERIFY_USER",
        "situationSummary": "AI/RAG 분석 실패로 로컬 보수 판단을 적용합니다.",
        "reasoning": reason,
        "verificationMessage": "괜찮으십니까? 괜찮으시다면 '네'라고 대답해주세요.",
        "timeoutSec": 10,
    }


def request_ai_analysis(event: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(
        AI_ANALYZE_URL,
        json=event,
        timeout=REQUEST_TIMEOUT_SEC,
    )
    response.raise_for_status()
    return response.json()


def on_message(mqtt_client, userdata, msg) -> None:
    try:
        event = parse_json_message(msg)
        print(f"{TOPIC_EVENT_CANDIDATE} 수신: {event}")

        try:
            result = request_ai_analysis(event)
        except Exception as exc:
            result = fallback_result(event, f"AI/RAG REST 요청 실패: {exc}")

        publish_json(mqtt_client, TOPIC_ANALYSIS_RESULT, result)
        print(f"{TOPIC_ANALYSIS_RESULT} 발행: {result}")

    except Exception as exc:
        print(f"analysis_bridge 처리 오류: {exc}")


client.subscribe(TOPIC_EVENT_CANDIDATE, qos=1)
client.on_message = on_message

print("analysis_bridge 실행 중...")
print(f"subscribe: {TOPIC_EVENT_CANDIDATE}")
print(f"REST API: {AI_ANALYZE_URL}")
print(f"publish: {TOPIC_ANALYSIS_RESULT}")
client.loop_forever()

"""MQTT-to-REST bridge for AI/RAG analysis.

Flow:
/event/candidate  --MQTT-->  analysis_bridge.py
analysis_bridge.py --REST--> AI/RAG server
AI/RAG response    --MQTT-->  /analysis/result

The /analysis/result contract follows the final SRS change set:
analysisReason + verificationPlan + analysisStatus.
"""

from datetime import datetime, timezone
from typing import Any, Dict

import requests

from config import (
    AI_ANALYZE_URL,
    DEFAULT_PROMPT_ASSET,
    DEFAULT_VERIFICATION_TIMEOUT_SEC,
    REQUEST_TIMEOUT_SEC,
    TOPIC_ANALYSIS_RESULT,
    TOPIC_EVENT_CANDIDATE,
)
from enums import DEFAULT_EXPECTED_OK_TEXT
from mqtt_client import create_mqtt_client, parse_json_message, publish_json


client = create_mqtt_client("analysis-bridge")


def now_iso_millis() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def fallback_result(event: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """Build an SRS-compliant fallback /analysis/result."""
    return {
        "type": "analysis.result",
        "eventId": event.get("eventId"),
        "timestamp": now_iso_millis(),
        "isFall": True,
        "confidence": 0.6,
        "riskLevel": "MEDIUM",
        "recommendedAction": "VERIFY_USER",
        "situationSummary": "AI/RAG 분석 실패로 엣지 rule-based 판단을 기반으로 사용자 확인 절차를 수행합니다.",
        "analysisReason": reason,
        "verificationPlan": {
            "required": True,
            "method": "LOCAL_MP3_STT",
            "promptAsset": DEFAULT_PROMPT_ASSET,
            "expectedOkText": DEFAULT_EXPECTED_OK_TEXT,
            "timeoutSec": DEFAULT_VERIFICATION_TIMEOUT_SEC,
        },
        "analysisStatus": "FALLBACK_RULE",
    }


def normalize_analysis_result(result: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """Keep backward compatibility with old AI responses while publishing the final contract."""
    normalized = dict(result)
    normalized["type"] = "analysis.result"
    normalized["eventId"] = normalized.get("eventId") or event.get("eventId")
    normalized["timestamp"] = normalized.get("timestamp") or now_iso_millis()

    if "analysisReason" not in normalized:
        normalized["analysisReason"] = normalized.pop("reasoning", "")
    else:
        normalized.pop("reasoning", None)

    if "verificationPlan" not in normalized:
        action = normalized.get("recommendedAction", "VERIFY_USER")
        requires_verification = action == "VERIFY_USER"
        normalized["verificationPlan"] = {
            "required": requires_verification,
            "method": "LOCAL_MP3_STT" if requires_verification else "NONE",
            "promptAsset": DEFAULT_PROMPT_ASSET if requires_verification else None,
            "expectedOkText": DEFAULT_EXPECTED_OK_TEXT if requires_verification else [],
            "timeoutSec": int(normalized.pop("timeoutSec", DEFAULT_VERIFICATION_TIMEOUT_SEC)) if requires_verification else 0,
        }
    else:
        normalized.pop("verificationMessage", None)
        normalized.pop("timeoutSec", None)

    normalized.setdefault("analysisStatus", "SUCCESS")
    return normalized


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
            result = normalize_analysis_result(request_ai_analysis(event), event)
        except Exception as exc:
            result = fallback_result(event, f"AI/RAG REST 요청 실패 또는 응답 정규화 실패: {exc}")

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

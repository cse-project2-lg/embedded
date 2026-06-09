"""Response module for final SRS analysis results.

Flow:
/analysis/result --MQTT--> response_manager.py
response_manager.py handles local MP3 prompt + STT decision
response_manager.py --REST--> cloud notification service when escalation is needed
response_manager.py --MQTT--> /response/outcome

The edge device does not directly send Kakao/SMS. It sends notification.request
to the cloud service and records the returned notification.result in
/response/outcome.
"""

from __future__ import annotations
from pathlib import Path

import os

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import requests

from config import (
    DEFAULT_NOTIFICATION_CHANNELS,
    DEFAULT_PROMPT_ASSET,
    DEFAULT_VERIFICATION_TIMEOUT_SEC,
    DEVICE_ID,
    NOTIFICATION_REQUEST_URL,
    NOTIFICATION_TIMEOUT_SEC,
    ROOM_ID,
    TOPIC_ANALYSIS_RESULT,
    TOPIC_RESPONSE_OUTCOME,
)
from enums import (
    DEFAULT_EXPECTED_OK_TEXT,
    HELP_KEYWORDS,
    NOT_OK_KEYWORDS,
    NOTIFICATION_STATUSES,
    RECOMMENDED_ACTIONS,
    USER_RESPONSES,
)
from mqtt_client import create_mqtt_client, parse_json_message, publish_json

import pygame
import time

import whisper
import sounddevice as sd

from scipy.io.wavfile import write

pygame.mixer.init(
    frequency=48000,
    channels=2
)

print("Whisper 모델 로딩...")
model = whisper.load_model("tiny")
print("Whisper 모델 로딩 완료")

BASE_DIR = Path(__file__).resolve().parent
WARNING_SOUND = BASE_DIR / "sounds" / "warning.mp3"

client = create_mqtt_client("response-manager")
def now_iso_millis() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def normalize_text(text: str) -> str:
    """Normalize STT text for simple keyword matching."""
    return re.sub(r"[\s\.,!?~'\"“”‘’]+", "", text or "").lower()


def contains_any(normalized_text: str, keywords: List[str]) -> bool:
    return any(normalize_text(keyword) in normalized_text for keyword in keywords if keyword)


def classify_user_response(transcript: str, expected_ok_text: List[str]) -> str:
    """Classify STT transcript according to verificationPlan.expectedOkText.

    도움 요청/이상 상태 표현을 OK보다 우선한다.
    """
    normalized = normalize_text(transcript)
    if not normalized:
        return "NO_RESPONSE"

    if contains_any(normalized, HELP_KEYWORDS):
        return "HELP"

    if contains_any(normalized, NOT_OK_KEYWORDS):
        return "NOT_OK"

    ok_terms = expected_ok_text or DEFAULT_EXPECTED_OK_TEXT
    if contains_any(normalized, ok_terms):
        return "OK"

    return "UNCLEAR"


def play_prompt_asset(prompt_asset: str) -> None:

    asset_path = Path(prompt_asset)

    if not asset_path.is_absolute():
        asset_path = BASE_DIR / "sounds" / asset_path.name

    if not asset_path.exists():
        print(f"MP3 파일을 찾을 수 없음: {asset_path}")
        return

    print(f"MP3 재생: {asset_path}")

    pygame.mixer.music.load(str(asset_path))
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        time.sleep(0.1)

    print(f"MP3 재생 완료: {asset_path}")


def listen_user_transcript(timeout_sec: int) -> str:

    os.makedirs("recordings", exist_ok=True)

    print(f"사용자 음성 응답 대기: {timeout_sec}초")

    sample_rate = 48000
    device_id = 1

    audio_file = "recordings/response.wav"

    recording = sd.rec(
        int(timeout_sec * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        device=device_id
    )

    sd.wait()

    write(audio_file, sample_rate, recording)

    result = model.transcribe(
        audio_file,
        language="ko",
        fp16=False
    )

    transcript = result["text"].strip()

    print(f"STT 결과: {transcript}")

    return transcript


def build_verification_record(
    verification_plan: Dict[str, Any],
    asked: bool,
    timeout_sec: int,
) -> Dict[str, Any]:
    return {
        "method": verification_plan.get("method", "NONE"),
        "promptAsset": verification_plan.get("promptAsset"),
        "asked": asked,
        "timeoutSec": timeout_sec,
    }


def build_notification_request(
    result: Dict[str, Any],
    verification_plan: Dict[str, Any],
    user_response: str,
    transcript: str,
    asked: bool,
    escalation_reason: str,
    message: str,
) -> Dict[str, Any]:
    return {
        "type": "notification.request",
        "eventId": result.get("eventId"),
        "timestamp": now_iso_millis(),
        "deviceId": result.get("deviceId") or DEVICE_ID,
        "roomId": result.get("roomId") or ROOM_ID,
        "riskLevel": result.get("riskLevel", "HIGH"),
        "situationSummary": result.get("situationSummary", ""),
        "escalationReason": escalation_reason,
        "verification": {
            "method": verification_plan.get("method", "NONE"),
            "promptAsset": verification_plan.get("promptAsset"),
            "asked": asked,
            "userResponse": user_response,
            "transcript": transcript,
            "timeoutSec": int(verification_plan.get("timeoutSec") or 0),
        },
        "notification": {
            "channels": DEFAULT_NOTIFICATION_CHANNELS,
            "message": message,
        },
    }


def request_guardian_notification(notification_request: Dict[str, Any]) -> Dict[str, Any]:
    """Send notification.request to the cloud notification service."""
    try:
        response = requests.post(
            NOTIFICATION_REQUEST_URL,
            json=notification_request,
            timeout=NOTIFICATION_TIMEOUT_SEC,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return {
            "type": "notification.result",
            "eventId": notification_request.get("eventId"),
            "timestamp": now_iso_millis(),
            "notificationStatus": "FAILED",
            "channels": notification_request.get("notification", {}).get("channels", []),
            "attemptCount": 1,
            "error": f"NOTIFICATION_REQUEST_FAILED: {exc}",
        }

    payload.setdefault("type", "notification.result")
    payload.setdefault("eventId", notification_request.get("eventId"))
    payload.setdefault("timestamp", now_iso_millis())
    payload.setdefault("channels", notification_request.get("notification", {}).get("channels", []))
    payload.setdefault("attemptCount", 1)
    payload.setdefault("error", None)

    if payload.get("notificationStatus") not in NOTIFICATION_STATUSES:
        payload["notificationStatus"] = "FAILED"
        payload["error"] = payload.get("error") or "INVALID_NOTIFICATION_STATUS"

    return payload


def notification_to_outcome_fields(notification_result: Dict[str, Any]) -> Tuple[str, Dict[str, Any], str]:
    status = notification_result.get("notificationStatus", "FAILED")
    notification = {
        "channels": notification_result.get("channels", []),
        "attemptCount": int(notification_result.get("attemptCount") or 0),
        "error": notification_result.get("error"),
    }
    response_outcome = "ESCALATED_TO_GUARDIAN" if status == "SENT" else "NOTIFICATION_FAILED"
    return status, notification, response_outcome


def build_response_outcome(
    result: Dict[str, Any],
    user_response: str,
    transcript: str,
    verification: Dict[str, Any],
    response_outcome: str,
    notification_status: str,
    notification: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "type": "response.outcome",
        "eventId": result.get("eventId"),
        "timestamp": now_iso_millis(),
        "recommendedAction": result.get("recommendedAction", "OBSERVE"),
        "userResponse": user_response,
        "transcript": transcript,
        "verification": verification,
        "responseOutcome": response_outcome,
        "notificationStatus": notification_status,
        "notification": notification,
    }


def handle_analysis_result(result: Dict[str, Any]) -> Dict[str, Any]:
    action = result.get("recommendedAction", "OBSERVE")
    if action not in RECOMMENDED_ACTIONS:
        action = "VERIFY_USER"

    verification_plan = result.get("verificationPlan")
    if not isinstance(verification_plan, dict):
        verification_plan = {
            "required": action == "VERIFY_USER",
            "method": "LOCAL_MP3_STT" if action == "VERIFY_USER" else "NONE",
            "promptAsset": DEFAULT_PROMPT_ASSET if action == "VERIFY_USER" else None,
            "expectedOkText": DEFAULT_EXPECTED_OK_TEXT if action == "VERIFY_USER" else [],
            "timeoutSec": DEFAULT_VERIFICATION_TIMEOUT_SEC if action == "VERIFY_USER" else 0,
        }

    user_response = "NOT_ASKED"
    transcript = ""
    asked = False
    timeout_sec = int(verification_plan.get("timeoutSec") or 0)
    verification = build_verification_record(verification_plan, asked=False, timeout_sec=timeout_sec)

    if action == "NO_ACTION":
        return build_response_outcome(
            result=result,
            user_response=user_response,
            transcript=transcript,
            verification=verification,
            response_outcome="NORMAL_CLOSED",
            notification_status="NOT_REQUIRED",
            notification={"channels": [], "attemptCount": 0, "error": None},
        )

    if action == "OBSERVE":
        return build_response_outcome(
            result=result,
            user_response=user_response,
            transcript=transcript,
            verification=verification,
            response_outcome="OBSERVING",
            notification_status="NOT_REQUIRED",
            notification={"channels": [], "attemptCount": 0, "error": None},
        )

    if action == "VERIFY_USER" and verification_plan.get("required", False):
        prompt_asset = verification_plan.get("promptAsset") or DEFAULT_PROMPT_ASSET
        timeout_sec = int(verification_plan.get("timeoutSec") or DEFAULT_VERIFICATION_TIMEOUT_SEC)
        expected_ok_text = verification_plan.get("expectedOkText") or DEFAULT_EXPECTED_OK_TEXT

        play_prompt_asset(prompt_asset)
        asked = True
        transcript = listen_user_transcript(timeout_sec)
        user_response = classify_user_response(transcript, expected_ok_text)
        if user_response not in USER_RESPONSES:
            user_response = "UNCLEAR"

        verification = build_verification_record(
            {**verification_plan, "promptAsset": prompt_asset},
            asked=True,
            timeout_sec=timeout_sec,
        )

        if user_response == "OK":
            return build_response_outcome(
                result=result,
                user_response=user_response,
                transcript=transcript,
                verification=verification,
                response_outcome="VERIFIED_OK_CLOSED",
                notification_status="NOT_REQUIRED",
                notification={"channels": [], "attemptCount": 0, "error": None},
            )

        escalation_reason = "사용자 확인 질문 후 정상 응답이 확인되지 않았습니다."
        if user_response == "HELP":
            escalation_reason = "사용자 음성에서 도움 요청 표현이 감지되었습니다."
        elif user_response == "NOT_OK":
            escalation_reason = "사용자 음성에서 이상 상태 또는 부정 응답이 감지되었습니다."
        elif user_response == "NO_RESPONSE":
            escalation_reason = "사용자 확인 질문 후 응답 제한 시간 내 음성 응답이 수신되지 않았습니다."
        elif user_response == "UNCLEAR":
            escalation_reason = "STT 결과가 불명확하여 정상 응답으로 판단할 수 없습니다."

        notification_request = build_notification_request(
            result=result,
            verification_plan={**verification_plan, "promptAsset": prompt_asset},
            user_response=user_response,
            transcript=transcript,
            asked=True,
            escalation_reason=escalation_reason,
            message="낙상 의심 상황이 발생했으며 사용자의 정상 응답이 확인되지 않았습니다.",
        )
        notification_result = request_guardian_notification(notification_request)
        notification_status, notification, response_outcome = notification_to_outcome_fields(notification_result)

        return build_response_outcome(
            result=result,
            user_response=user_response,
            transcript=transcript,
            verification=verification,
            response_outcome=response_outcome,
            notification_status=notification_status,
            notification=notification,
        )

    # NOTIFY_GUARDIAN or VERIFY_USER without a usable verification device.
    user_response = "NOT_ASKED"
    verification_plan = {**verification_plan, "method": verification_plan.get("method") or "NONE"}
    verification = build_verification_record(verification_plan, asked=False, timeout_sec=0)
    escalation_reason = "recommendedAction이 NOTIFY_GUARDIAN이거나 사용자 확인 절차를 수행할 수 없어 즉시 보호자 알림을 요청합니다."
    notification_request = build_notification_request(
        result=result,
        verification_plan={"method": "NONE", "promptAsset": None, "timeoutSec": 0},
        user_response=user_response,
        transcript=transcript,
        asked=False,
        escalation_reason=escalation_reason,
        message="고위험 낙상 의심 상황이 발생했습니다. 즉시 확인이 필요합니다.",
    )
    notification_result = request_guardian_notification(notification_request)
    notification_status, notification, response_outcome = notification_to_outcome_fields(notification_result)

    return build_response_outcome(
        result=result,
        user_response=user_response,
        transcript=transcript,
        verification=verification,
        response_outcome=response_outcome,
        notification_status=notification_status,
        notification=notification,
    )


def on_message(mqtt_client, userdata, msg) -> None:
    try:
        result = parse_json_message(msg)
        print(f"{TOPIC_ANALYSIS_RESULT} 수신: {result}")

        outcome = handle_analysis_result(result)
        publish_json(mqtt_client, TOPIC_RESPONSE_OUTCOME, outcome)
        print(f"{TOPIC_RESPONSE_OUTCOME} 발행: {outcome}")

    except Exception as exc:
        print(f"response_manager 처리 오류: {exc}")


client.subscribe(TOPIC_ANALYSIS_RESULT, qos=1)
client.on_message = on_message

print("response_manager 실행 중...")
print(f"subscribe: {TOPIC_ANALYSIS_RESULT}")
print(f"notification REST: {NOTIFICATION_REQUEST_URL}")
print(f"publish: {TOPIC_RESPONSE_OUTCOME}")
client.loop_forever()

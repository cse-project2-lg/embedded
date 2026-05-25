"""Response module for AI/RAG analysis results.

Flow:
/analysis/result --MQTT--> response_manager.py
response_manager.py handles TTS/STT/notification decision
response_manager.py --MQTT--> /response/outcome

TTS, STT and notification are currently stubbed so the team can connect real
speaker/microphone/Kakao/SMS logic later without changing the JSON contract.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from config import (
    DEFAULT_NOTIFICATION_CHANNELS,
    DEFAULT_VERIFICATION_TIMEOUT_SEC,
    TOPIC_ANALYSIS_RESULT,
    TOPIC_RESPONSE_OUTCOME,
)
from mqtt_client import create_mqtt_client, parse_json_message, publish_json


client = create_mqtt_client("response-manager")

VALID_ACTIONS = {"NO_ACTION", "OBSERVE", "VERIFY_USER", "NOTIFY_GUARDIAN"}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def play_tts(message: str) -> None:
    # TODO: connect gTTS, pyttsx3, or local speaker output.
    print(f"TTS 출력 예정: {message}")


def listen_user_response(timeout_sec: int) -> Tuple[str, str]:
    # TODO: connect microphone + STT.
    # Return examples:
    #   ("OK", "네 괜찮아요")
    #   ("HELP", "도와줘")
    #   ("NO_RESPONSE", "")
    #   ("UNCLEAR", "...")
    print(f"사용자 응답 대기: {timeout_sec}초")
    return "NO_RESPONSE", ""


def send_guardian_notification(channels: List[str], result: Dict[str, Any]) -> bool:
    # TODO: connect Kakao/SMS REST API.
    print(f"보호자 알림 전송 예정: channels={channels}, eventId={result.get('eventId')}")
    return True


def handle_analysis_result(result: Dict[str, Any]) -> Dict[str, Any]:
    action = result.get("recommendedAction", "OBSERVE")
    if action not in VALID_ACTIONS:
        action = "VERIFY_USER"

    event_id = result.get("eventId")
    user_response = "NOT_ASKED"
    transcript = ""
    final_state = "NORMAL"
    notification_sent = False
    channels: List[str] = []

    if action == "NO_ACTION":
        final_state = "NORMAL"

    elif action == "OBSERVE":
        final_state = "OBSERVING"

    elif action == "VERIFY_USER":
        message = result.get("verificationMessage") or "괜찮으십니까? 괜찮으시다면 '네'라고 대답해주세요."
        timeout_sec = int(result.get("timeoutSec") or DEFAULT_VERIFICATION_TIMEOUT_SEC)

        play_tts(message)
        user_response, transcript = listen_user_response(timeout_sec)

        if user_response == "OK":
            final_state = "CANCELED_BY_USER"
        else:
            final_state = "EMERGENCY_CONFIRMED"
            channels = DEFAULT_NOTIFICATION_CHANNELS
            notification_sent = send_guardian_notification(channels, result)
            if not notification_sent:
                final_state = "NOTIFICATION_FAILED"

    elif action == "NOTIFY_GUARDIAN":
        final_state = "EMERGENCY_CONFIRMED"
        channels = DEFAULT_NOTIFICATION_CHANNELS
        notification_sent = send_guardian_notification(channels, result)
        if not notification_sent:
            final_state = "NOTIFICATION_FAILED"

    return {
        "eventId": event_id,
        "timestamp": now_iso(),
        "userResponse": user_response,
        "transcript": transcript,
        "finalState": final_state,
        "notification": {
            "sent": notification_sent,
            "channels": channels,
        },
    }


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
print(f"publish: {TOPIC_RESPONSE_OUTCOME}")
client.loop_forever()

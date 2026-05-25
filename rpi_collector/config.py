"""Runtime configuration for the Raspberry Pi edge modules.

MQTT is used only inside the edge device. The AI/RAG server is called through
HTTP by analysis_bridge.py.
"""
from dotenv import load_dotenv
import os

load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

TOPIC_EVENT_CANDIDATE = os.getenv("TOPIC_EVENT_CANDIDATE", "/event/candidate")
TOPIC_ANALYSIS_RESULT = os.getenv("TOPIC_ANALYSIS_RESULT", "/analysis/result")
TOPIC_RESPONSE_OUTCOME = os.getenv("TOPIC_RESPONSE_OUTCOME", "/response/outcome")

AI_ANALYZE_URL = os.getenv(
    "AI_ANALYZE_URL",
    "http://127.0.0.1:8000/api/v1/fall-events/analyze",
)

DEVICE_ID = os.getenv("DEVICE_ID", "RPi4-001")
ROOM_ID = os.getenv("ROOM_ID", "living-room")

REQUEST_TIMEOUT_SEC = float(os.getenv("REQUEST_TIMEOUT_SEC", "30"))
DEFAULT_VERIFICATION_TIMEOUT_SEC = int(os.getenv("DEFAULT_VERIFICATION_TIMEOUT_SEC", "10"))

# MVP notification channels. Replace this with real Kakao/SMS integration later.
DEFAULT_NOTIFICATION_CHANNELS = [
    channel.strip()
    for channel in os.getenv("DEFAULT_NOTIFICATION_CHANNELS", "KAKAO,SMS").split(",")
    if channel.strip()
]

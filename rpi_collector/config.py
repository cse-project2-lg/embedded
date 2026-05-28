"""Runtime configuration for the Raspberry Pi edge modules.

MQTT is used for local edge topics. Cloud AI/RAG and cloud notification are
called through HTTP by analysis_bridge.py and response_manager.py.
"""
from dotenv import load_dotenv
import os

load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# ESP32 raw PIR/ToF samples.
TOPIC_SENSOR_RAW = os.getenv("TOPIC_SENSOR_RAW", "/sensor/raw")
TOPIC_EVENT_CANDIDATE = os.getenv("TOPIC_EVENT_CANDIDATE", "/event/candidate")
TOPIC_ANALYSIS_RESULT = os.getenv("TOPIC_ANALYSIS_RESULT", "/analysis/result")
TOPIC_RESPONSE_OUTCOME = os.getenv("TOPIC_RESPONSE_OUTCOME", "/response/outcome")

AI_ANALYZE_URL = os.getenv(
    "AI_ANALYZE_URL",
    "http://127.0.0.1:8000/api/v1/fall-events/analyze",
)
NOTIFICATION_REQUEST_URL = os.getenv(
    "NOTIFICATION_REQUEST_URL",
    "http://127.0.0.1:8000/api/v1/notifications/guardian",
)

DEVICE_ID = os.getenv("DEVICE_ID", "RPi4-001")
ROOM_ID = os.getenv("ROOM_ID", "living-room")

REQUEST_TIMEOUT_SEC = float(os.getenv("REQUEST_TIMEOUT_SEC", "30"))
NOTIFICATION_TIMEOUT_SEC = float(os.getenv("NOTIFICATION_TIMEOUT_SEC", "10"))
DEFAULT_VERIFICATION_TIMEOUT_SEC = int(os.getenv("DEFAULT_VERIFICATION_TIMEOUT_SEC", "10"))
DEFAULT_PROMPT_ASSET = os.getenv("DEFAULT_PROMPT_ASSET", "are_you_ok_ko.mp3")

# Stub STT input for integration tests. Empty value means no response.
STUB_STT_TRANSCRIPT = os.getenv("STUB_STT_TRANSCRIPT", "")

# Raw input logging. This is not preprocessing; it is only for debugging/replay.
RAW_LOG_DIR = os.getenv("RAW_LOG_DIR", "./data/raw_sensor_logs")
RAW_LOG_ENABLED = os.getenv("RAW_LOG_ENABLED", "true").lower() in {"1", "true", "yes", "y"}

# MVP notification channels. Replace this with real Kakao/SMS integration later.
DEFAULT_NOTIFICATION_CHANNELS = [
    channel.strip()
    for channel in os.getenv("DEFAULT_NOTIFICATION_CHANNELS", "KAKAO,SMS").split(",")
    if channel.strip()
]

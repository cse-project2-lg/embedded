"""Manual publisher for integration testing.

Run this when the preprocessing module is not ready yet. In production, the
preprocessing/synchronization module should publish the same JSON shape to
/event/candidate.
"""

from datetime import datetime, timezone

from config import DEVICE_ID, ROOM_ID, TOPIC_EVENT_CANDIDATE
from mqtt_client import create_mqtt_client, publish_json


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


sample_event = {
    "eventId": "EVT-TEST-001",
    "timestamp": now_iso(),
    "deviceId": DEVICE_ID,
    "roomId": ROOM_ID,
    "sensorSummary": {
        "pirMotion": False,
        "pirLastMotionMs": 2400,
        "tofDistanceMm": 1820,
        "tofChangeMm": 680,
        "tofStableMs": 2100,
        "csiChangeScore": 0.82,
        "csiPacketCount": 57,
    },
    "localScore": 0.86,
}

client = create_mqtt_client("candidate-example-publisher")
publish_json(client, TOPIC_EVENT_CANDIDATE, sample_event)
print(f"{TOPIC_EVENT_CANDIDATE} 발행 완료: {sample_event}")
client.disconnect()

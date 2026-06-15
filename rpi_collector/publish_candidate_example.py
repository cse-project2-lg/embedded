"""Manual /event/candidate publisher for MQTT integration testing.

Run this when the preprocessing/synchronization module is not ready yet.
In production, the preprocessing/synchronization module should create the same
JSON shape and call event_candidate_publisher.publish_event_candidate().
"""

from config import DEVICE_ID, ROOM_ID
from event_candidate_contract import build_sample_candidate
from event_candidate_publisher import publish_event_candidate


sample_event = build_sample_candidate(DEVICE_ID, ROOM_ID)
publish_event_candidate(sample_event)
print(f"/event/candidate 발행 완료: {sample_event}")

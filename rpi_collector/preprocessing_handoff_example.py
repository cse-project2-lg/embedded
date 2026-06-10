"""Example showing how the preprocessing/synchronization module can attach.

This file is not the real preprocessor. It only demonstrates the integration
contract: raw_mqtt_subscriber delivers each valid /sensor/raw or /csi/raw record
through a callback immediately after validation and timestamp enrichment.
"""

from __future__ import annotations

from queue import Queue
from typing import Any, Dict

from raw_mqtt_subscriber import run_subscriber

preprocessing_queue: "Queue[Dict[str, Any]]" = Queue()


def enqueue_to_preprocessor(raw_record: Dict[str, Any]) -> None:
    """Replace this function with the actual synchronization team's queue put."""
    preprocessing_queue.put(raw_record)
    print(
        "HANDOFF TO PREPROCESSOR "
        f"topic={raw_record.get('mqttTopic')} "
        f"seq={raw_record.get('seq')} "
        f"receivedNs={raw_record.get('mqttReceivedMonotonicNs')}"
    )


def main() -> None:
    run_subscriber(on_valid_message=enqueue_to_preprocessor)


if __name__ == "__main__":
    main()

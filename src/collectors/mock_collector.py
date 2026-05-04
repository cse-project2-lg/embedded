from __future__ import annotations

import random
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from collectors.base import BaseCollector


class MockCollector(BaseCollector):
    """
    회로 완성 전 사용하는 Mock 센서 수집기.
    - PIR: 움직임 감지 여부 0/1
    - ToF: 거리값(mm)
    - CSI: 변화량/분산/RSSI 형태의 요약값
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.device_id = config["device"]["device_id"]
        self.room_id = config["device"]["room_id"]
        self.mock_config = config["mock"]
        self.prev_tof = random.randint(
            self.mock_config["normal_tof_min_mm"],
            self.mock_config["normal_tof_max_mm"],
        )

    def read(self) -> Dict[str, Any]:
        is_fall_like = random.random() < self.mock_config["fall_probability"]

        if is_fall_like:
            tof = random.randint(
                self.mock_config["fall_tof_min_mm"],
                self.mock_config["fall_tof_max_mm"],
            )
            pir_motion = random.choice([0, 1])
            csi_change = round(random.uniform(0.78, 0.98), 3)
            csi_variance = round(random.uniform(0.65, 0.95), 3)
            label = "fall_like"
        else:
            tof = random.randint(
                self.mock_config["normal_tof_min_mm"],
                self.mock_config["normal_tof_max_mm"],
            )
            pir_motion = random.choice([0, 1])
            csi_change = round(random.uniform(0.05, 0.55), 3)
            csi_variance = round(random.uniform(0.05, 0.45), 3)
            label = "normal_like"

        tof_delta = tof - self.prev_tof
        self.prev_tof = tof

        return {
            "messageId": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "sensor.raw",
            "source": "mock_collector",
            "deviceId": self.device_id,
            "roomId": self.room_id,
            "payload": {
                "csi": {
                    "rssi": random.randint(
                        self.mock_config["rssi_min"],
                        self.mock_config["rssi_max"],
                    ),
                    "change": csi_change,
                    "variance": csi_variance,
                    "raw": None,
                },
                "pir": {
                    "sensorId": "pir_01",
                    "motion": pir_motion,
                },
                "tof": {
                    "sensorId": "tof_01",
                    "distanceMm": tof,
                    "deltaMm": tof_delta,
                },
                "mockLabel": label,
            },
        }

from __future__ import annotations

import csv
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from collectors.base import BaseCollector


class WiFallCollector(BaseCollector):
    """
    WiFall CSV 파일을 CSI Mock 데이터로 사용하는 수집기.
    실제 Hugging Face 데이터셋을 CSV로 내려받은 뒤 경로를 넘기면 된다.

    기대 컬럼 예시:
    - timestamp
    - rssi
    - data 또는 csi_data
    - target 또는 label

    컬럼명이 달라도 가능한 범위에서 자동 추정한다.
    """

    def __init__(self, config: Dict[str, Any], csv_path: str):
        self.config = config
        self.device_id = config["device"]["device_id"]
        self.room_id = config["device"]["room_id"]
        self.rows = self._load_rows(csv_path)
        self.index = 0
        self.prev_tof = random.randint(900, 1700)

        if not self.rows:
            raise ValueError(f"WiFall CSV has no rows: {csv_path}")

    def _load_rows(self, csv_path: str) -> List[Dict[str, str]]:
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"WiFall CSV not found: {path}")

        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _get_value(self, row: Dict[str, str], candidates: List[str], default=None):
        lowered = {k.lower(): k for k in row.keys()}
        for cand in candidates:
            key = lowered.get(cand.lower())
            if key is not None:
                return row.get(key)
        return default

    def _is_fall_label(self, label: str) -> bool:
        normalized = str(label).lower()
        return any(word in normalized for word in ["fall", "fallen", "낙상", "1"])

    def read(self) -> Dict[str, Any]:
        row = self.rows[self.index]
        self.index = (self.index + 1) % len(self.rows)

        label = self._get_value(row, ["target", "taget", "label", "activity"], "unknown")
        is_fall = self._is_fall_label(label)

        try:
            rssi = int(float(self._get_value(row, ["rssi"], random.randint(-75, -35))))
        except (TypeError, ValueError):
            rssi = random.randint(-75, -35)

        csi_raw = self._get_value(row, ["data", "csi_data", "csi", "CSI_DATA"], None)

        # WiFall은 CSI용으로 사용하고, PIR/ToF는 라벨에 맞춰 보조 Mock 생성
        if is_fall:
            tof = random.randint(250, 650)
            pir_motion = random.choice([0, 1])
            csi_change = round(random.uniform(0.78, 0.98), 3)
            csi_variance = round(random.uniform(0.65, 0.95), 3)
        else:
            tof = random.randint(900, 1700)
            pir_motion = random.choice([0, 1])
            csi_change = round(random.uniform(0.05, 0.55), 3)
            csi_variance = round(random.uniform(0.05, 0.45), 3)

        tof_delta = tof - self.prev_tof
        self.prev_tof = tof

        return {
            "messageId": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "sensor.raw",
            "source": "wifall_collector",
            "deviceId": self.device_id,
            "roomId": self.room_id,
            "payload": {
                "csi": {
                    "rssi": rssi,
                    "change": csi_change,
                    "variance": csi_variance,
                    "raw": csi_raw,
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

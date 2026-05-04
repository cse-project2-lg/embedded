from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from collectors.base import BaseCollector


class HardwareCollector(BaseCollector):
    """
    실제 회로 연결 후 교체할 수집기.
    현재는 코드 구조만 제공한다.

    예상 연결:
    - PIR: GPIO 디지털 입력
    - ToF VL53L0X: I2C
    - CSI: nexmon_csi 또는 별도 수집 프로세스 결과 연동
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.device_id = config["device"]["device_id"]
        self.room_id = config["device"]["room_id"]

        # 실제 회로 연결 후 아래 라이브러리 사용 예시
        # import RPi.GPIO as GPIO
        # import board
        # import busio
        # import adafruit_vl53l0x
        #
        # self.pir_pin = 17
        # GPIO.setmode(GPIO.BCM)
        # GPIO.setup(self.pir_pin, GPIO.IN)
        #
        # i2c = busio.I2C(board.SCL, board.SDA)
        # self.tof = adafruit_vl53l0x.VL53L0X(i2c)

        self.prev_tof = None

    def read(self) -> Dict[str, Any]:
        # 실제 센서 연결 후 아래 값을 교체한다.
        # pir_motion = GPIO.input(self.pir_pin)
        # tof_distance = int(self.tof.range)
        # csi_summary = read_csi_summary_from_nexmon_log()

        raise NotImplementedError(
            "HardwareCollector는 회로 연결 후 PIR/ToF/CSI 실제 읽기 코드로 채워야 합니다."
        )

    def build_message(self, pir_motion: int, tof_distance: int, csi_summary: Dict[str, Any]) -> Dict[str, Any]:
        if self.prev_tof is None:
            tof_delta = 0
        else:
            tof_delta = tof_distance - self.prev_tof
        self.prev_tof = tof_distance

        return {
            "messageId": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "sensor.raw",
            "source": "hardware_collector",
            "deviceId": self.device_id,
            "roomId": self.room_id,
            "payload": {
                "csi": csi_summary,
                "pir": {
                    "sensorId": "pir_01",
                    "motion": int(pir_motion),
                },
                "tof": {
                    "sensorId": "tof_01",
                    "distanceMm": int(tof_distance),
                    "deltaMm": int(tof_delta),
                },
            },
        }

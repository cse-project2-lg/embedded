"""Manual /sensor/raw publisher for RPi-side contract testing."""

import time

from config import TOPIC_SENSOR_RAW
from mqtt_client import create_mqtt_client, publish_json

sample_raw = {
    "type": "sensor.raw",
    "source": "esp32_sensor_node",
    "deviceId": "ESP32-001",
    "seq": 1,
    "sampleIntervalMs": 100,
    "sensors": {
        "pirMotion": True,
        "pirValue": 1,
        "tofDistanceMm": 1820,
        "tofValid": True,
        "tofTimeout": False,
        "tofError": None,
    },
    "transport": {
        "wifiRssiDbm": -55,
        "pingOk": True,
    },
}

client = create_mqtt_client("raw-example-publisher")
publish_json(client, TOPIC_SENSOR_RAW, sample_raw)
time.sleep(0.2)
client.disconnect()
print(f"{TOPIC_SENSOR_RAW} 발행 완료: {sample_raw}")

"""Small MQTT helper used by edge modules."""

import json
from typing import Any, Dict

import paho.mqtt.client as mqtt

from config import MQTT_HOST, MQTT_PORT


def create_mqtt_client(client_id: str) -> mqtt.Client:
    client = mqtt.Client(client_id=client_id)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    return client


def publish_json(client: mqtt.Client, topic: str, payload: Dict[str, Any], qos: int = 1) -> None:
    client.publish(
        topic,
        json.dumps(payload, ensure_ascii=False),
        qos=qos,
        retain=False,
    )


def parse_json_message(msg: mqtt.MQTTMessage) -> Dict[str, Any]:
    return json.loads(msg.payload.decode("utf-8"))

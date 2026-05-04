from __future__ import annotations

import json
import time
from typing import Dict, Any

import paho.mqtt.client as mqtt


class MqttPublisher:
    def __init__(self, config: Dict[str, Any], logger):
        self.config = config
        self.logger = logger
        self.mqtt_config = config["mqtt"]
        self.client = mqtt.Client(client_id=config["device"]["device_id"])
        self.connected = False

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        self.connected = rc == 0
        if self.connected:
            self.logger.info("MQTT connected")
        else:
            self.logger.error("MQTT connect failed rc=%s", rc)

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        self.logger.warning("MQTT disconnected rc=%s", rc)

    def connect(self):
        host = self.mqtt_config["broker_host"]
        port = int(self.mqtt_config["broker_port"])
        keepalive = int(self.mqtt_config["keepalive"])

        self.client.connect(host, port, keepalive)
        self.client.loop_start()

        for _ in range(20):
            if self.connected:
                return
            time.sleep(0.1)

        raise ConnectionError(f"MQTT broker connection timeout: {host}:{port}")

    def publish(self, topic_key: str, message: Dict[str, Any]):
        topic = self.mqtt_config["topics"][topic_key]
        qos = int(self.mqtt_config.get("qos", 1))
        payload = json.dumps(message, ensure_ascii=False)

        result = self.client.publish(topic, payload, qos=qos)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed topic={topic} rc={result.rc}")

        self.logger.info("published topic=%s type=%s", topic, message.get("type"))

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()

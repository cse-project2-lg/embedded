import json
import logging

import paho.mqtt.client as mqtt

from app.config import Settings
from app.influx_writer import InfluxWriter
from app.payload_mapper import csi_raw_to_point, sensor_raw_to_point


logger = logging.getLogger(__name__)


class MqttInfluxBridge:
    def __init__(self, settings: Settings, writer: InfluxWriter):
        self._settings = settings
        self._writer = writer

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info(
                "Connected to MQTT broker at %s:%s",
                self._settings.mqtt_broker,
                self._settings.mqtt_port,
            )

            topics = [
                (self._settings.sensor_raw_topic, 1),
                (self._settings.csi_raw_topic, 1),
            ]

            client.subscribe(topics)
            logger.info("Subscribed topics: %s", [topic for topic, _ in topics])
            return

        logger.error("Failed to connect to MQTT broker. reason_code=%s", reason_code)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        logger.warning("Disconnected from MQTT broker. reason_code=%s", reason_code)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic

        try:
            payload = msg.payload.decode("utf-8")
            data = json.loads(payload)

            if topic == self._settings.sensor_raw_topic:
                try:
                    point = sensor_raw_to_point(data)
                    self._writer.write_point(point)
                except (KeyError, ValueError, TypeError) as e:
                    logger.error("Payload validation failed for %s: %s", topic, e)
            elif topic == self._settings.csi_raw_topic:
                try:
                    point = csi_raw_to_point(data)
                    self._writer.write_point(point)
                except (KeyError, ValueError, TypeError) as e:
                    logger.error("Payload validation failed for %s: %s", topic, e)
            else:
                logger.warning("Unhandled MQTT topic: %s", topic)
                return

            logger.debug("InfluxDB point queued from topic=%s", topic)

        except json.JSONDecodeError:
            logger.exception("Invalid JSON payload. topic=%s", topic)
        except Exception:
            logger.exception("Failed to process MQTT message. topic=%s", topic)

    def start(self) -> None:
        logger.info(
            "Connecting to MQTT broker %s:%s",
            self._settings.mqtt_broker,
            self._settings.mqtt_port,
        )

        self._client.connect_async(
            self._settings.mqtt_broker,
            self._settings.mqtt_port,
            keepalive=60,
        )

        self._client.loop_forever()

    def stop(self) -> None:
        self._client.disconnect()
        logger.info("MQTT client disconnected.")
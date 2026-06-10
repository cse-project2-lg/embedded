import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

from app.config import Settings
from app.influx_writer import InfluxWriter
from app.payload_mapper import csi_raw_to_point, sensor_raw_to_point


logger = logging.getLogger(__name__)


class MqttInfluxBridge:
    def __init__(self, settings: Settings, writer: InfluxWriter):
        self._settings = settings
        self._writer = writer
        self._error_count = 0
        self._message_count = 0

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )

        self._client.reconnect_delay_set(min_delay=1, max_delay=120)

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
        if reason_code != 0:
            logger.warning("Unexpectedly disconnected from MQTT broker. reason_code=%s. Client will auto-reconnect.", reason_code)
            
            retry_count = 0
            max_retries = 5
            while retry_count < max_retries:
                try:
                    time.sleep(min(2 ** retry_count, 30))
                    client.reconnect()
                    break
                except Exception as e:
                    retry_count += 1
                    logger.warning("Manual reconnect attempt %d/%d failed: %s", retry_count, max_retries, e)
            if retry_count >= max_retries:
                logger.error("Manual reconnect failed after %d attempts", max_retries)
        else:
            logger.info("Cleanly disconnected from MQTT broker.")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        self._message_count += 1

        try:
            payload = msg.payload.decode("utf-8")
            data = json.loads(payload)

            wrote = False
            if topic == self._settings.sensor_raw_topic:
                try:
                    point = sensor_raw_to_point(data)
                    self._writer.write_point(point)
                    wrote = True
                except (KeyError, ValueError, TypeError) as e:
                    self._error_count += 1
                    logger.error("Payload validation failed for %s: %s", topic, e)
                    self._handle_dlq(topic, msg.payload, str(e))
            elif topic == self._settings.csi_raw_topic:
                try:
                    point = csi_raw_to_point(data)
                    self._writer.write_point(point)
                    wrote = True
                except (KeyError, ValueError, TypeError) as e:
                    self._error_count += 1
                    logger.error("Payload validation failed for %s: %s", topic, e)
                    self._handle_dlq(topic, msg.payload, str(e))
            else:
                logger.warning("Unhandled MQTT topic: %s", topic)
                return

            if wrote:
                logger.debug("InfluxDB point queued from topic=%s", topic)

            if self._message_count > 0 and (self._error_count / self._message_count) > 0.1:
                logger.critical("High error rate detected: %d/%d (%.1f%%) - check upstream data quality or schema changes",
                                self._error_count, self._message_count, 100.0 * self._error_count / self._message_count)

        except json.JSONDecodeError as e:
            self._error_count += 1
            logger.exception("Invalid JSON payload. topic=%s", topic)
            self._handle_dlq(topic, msg.payload, f"JSONDecodeError: {e}")
            if self._message_count > 0 and (self._error_count / self._message_count) > 0.1:
                logger.critical("High error rate detected: %d/%d (%.1f%%) - check upstream data quality or schema changes",
                                self._error_count, self._message_count, 100.0 * self._error_count / self._message_count)
        except Exception as e:
            self._error_count += 1
            logger.exception("Failed to process MQTT message. topic=%s", topic)
            self._handle_dlq(topic, msg.payload, f"UnexpectedException: {e}")
            if self._message_count > 0 and (self._error_count / self._message_count) > 0.1:
                logger.critical("High error rate detected: %d/%d (%.1f%%) - check upstream data quality or schema changes",
                                self._error_count, self._message_count, 100.0 * self._error_count / self._message_count)

    def _handle_dlq(self, topic: str, payload: bytes, reason: str) -> None:
        try:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d")
            dlq_path = Path(f"mqtt_dlq_{ts}.jsonl").resolve()
            dlq_record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "topic": topic,
                "reason": reason,
                "payload": payload.decode("utf-8", errors="replace")
            }
            with dlq_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(dlq_record, ensure_ascii=False) + "\n")
        except Exception as dlq_err:
            logger.error("Failed to write to Dead Letter Queue file: %s", dlq_err)

    def start(self) -> None:
        logger.info(
            "Connecting to MQTT broker %s:%s",
            self._settings.mqtt_broker,
            self._settings.mqtt_port,
        )

        retry_count = 0
        max_retries = 5
        while retry_count < max_retries:
            try:
                self._client.connect_async(
                    self._settings.mqtt_broker,
                    self._settings.mqtt_port,
                    keepalive=60,
                )
                break
            except Exception as e:
                retry_count += 1
                wait_time = min(2 ** retry_count, 30)
                logger.warning("Failed to connect to MQTT broker (attempt %d/%d): %s. Retrying in %ds...",
                               retry_count, max_retries, e, wait_time)
                time.sleep(wait_time)
        else:
            raise RuntimeError(f"Failed to connect to MQTT broker after {max_retries} attempts")

        self._client.loop_start()

    def stop(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()
        logger.info("MQTT client disconnected.")
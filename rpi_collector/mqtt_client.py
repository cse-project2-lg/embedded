"""Small MQTT helper used by edge modules."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt

from config import MQTT_HOST, MQTT_PORT


def _on_connect(client: mqtt.Client, userdata, flags, rc: int) -> None:
    if rc == 0:
        print(f"MQTT connected: {MQTT_HOST}:{MQTT_PORT}")
    else:
        print(f"MQTT connect failed: rc={rc}")


def _on_disconnect(client: mqtt.Client, userdata, rc: int) -> None:
    if rc != 0:
        print(f"MQTT disconnected unexpectedly: rc={rc}")


def create_mqtt_client(client_id: str) -> mqtt.Client:
    """Create and connect a paho MQTT client.

    The caller decides whether to run loop_forever() or loop_start().
    Long-running publishers such as csi_raw_collector.py should call
    loop_start() after creating the client so QoS delivery and reconnect
    processing can keep running while the UDP receive loop blocks.
    """
    client = mqtt.Client(client_id=client_id)
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    return client


def publish_json(
    client: mqtt.Client,
    topic: str,
    payload: Dict[str, Any],
    qos: int = 1,
    wait: bool = False,
    timeout: Optional[float] = 2.0,
) -> mqtt.MQTTMessageInfo:
    """Publish a JSON payload and optionally wait for QoS delivery.

    wait=False keeps the CSI receive loop fast. For one-shot scripts or tests,
    wait=True can be used to verify that the message leaves the client.
    """
    info = client.publish(
        topic,
        json.dumps(payload, ensure_ascii=False),
        qos=qos,
        retain=False,
    )
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"MQTT publish failed: topic={topic}, rc={info.rc}")
    if wait:
        info.wait_for_publish(timeout=timeout)
        if not info.is_published():
            raise TimeoutError(f"MQTT publish timeout: topic={topic}")
    return info


def parse_json_message(msg: mqtt.MQTTMessage) -> Dict[str, Any]:
    return json.loads(msg.payload.decode("utf-8"))

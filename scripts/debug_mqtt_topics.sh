#!/usr/bin/env bash
set -euo pipefail
MQTT_HOST="${MQTT_HOST:-127.0.0.1}"
MQTT_PORT="${MQTT_PORT:-1883}"
TOPIC_SENSOR_RAW="${TOPIC_SENSOR_RAW:-/sensor/raw}"
TOPIC_CSI_RAW="${TOPIC_CSI_RAW:-/csi/raw}"

echo "MQTT_HOST=$MQTT_HOST MQTT_PORT=$MQTT_PORT"
echo "watching $TOPIC_SENSOR_RAW and $TOPIC_CSI_RAW"
mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" -t "$TOPIC_SENSOR_RAW" -t "$TOPIC_CSI_RAW" -v

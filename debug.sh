#!/bin/bash

set -e

cd ~/workspace/embedded || exit 1

echo "[1/5] Monitoring /sensor/raw ..."
lxterminal --title="sensor_raw" \
-e "bash -c 'mosquitto_sub -h 127.0.0.1 -p 1883 -t \"/sensor/raw\" -v; exec bash'" &

sleep 1

echo "[2/5] Monitoring /preprocess/synced_frame ..."
lxterminal --title="synced_frame" \
-e "bash -c 'mosquitto_sub -h 127.0.0.1 -p 1883 -t \"/preprocess/synced_frame\" -v; exec bash'" &

sleep 1

echo "[3/5] Monitoring /event/candidate ..."
lxterminal --title="event_candidate" \
-e "bash -c 'mosquitto_sub -h 127.0.0.1 -p 1883 -t \"/event/candidate\" -v; exec bash'" &

sleep 1

echo "[4/5] Monitoring /analysis/result ..."
lxterminal --title="analysis_result" \
-e "bash -c 'mosquitto_sub -h 127.0.0.1 -p 1883 -t \"/analysis/result\" -v; exec bash'" &

sleep 1

echo "[5/5] Monitoring /response/outcome ..."
lxterminal --title="response_outcome" \
-e "bash -c 'mosquitto_sub -h 127.0.0.1 -p 1883 -t \"/response/outcome\" -v; exec bash'" &

echo ""
echo "MQTT debug monitors started."
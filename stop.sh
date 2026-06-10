#!/bin/bash

echo "Stopping edge services..."

pkill -f "response_manager.py" || true
pkill -f "analysis_bridge.py" || true
pkill -f "main_loop.py" || true

pkill -f "run_csi_raw_collector.sh" || true
pkill -f "run_synced_frame_builder.sh" || true

echo "Stopping MQTT monitors..."

pkill -f "mosquitto_sub" || true

echo "Stopping terminal windows..."

pkill -f "lxterminal" || true

echo ""
echo "All services stopped."
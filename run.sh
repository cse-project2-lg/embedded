#!/bin/bash

cd ~/workspace/embedded || exit 1

source venv/bin/activate

echo "[1/5] Starting response_manager..."
lxterminal -e "bash -c 'cd ~/workspace/embedded && source venv/bin/activate && python rpi_collector/response_manager.py; exec bash'" &

sleep 1

echo "[2/5] Starting analysis_bridge..."
lxterminal -e "bash -c 'cd ~/workspace/embedded && source venv/bin/activate && python rpi_collector/analysis_bridge.py; exec bash'" &

sleep 1

echo "[3/5] Starting main_loop..."
lxterminal -e "bash -c 'cd ~/workspace/embedded && source venv/bin/activate && python rpi_collector/main_loop.py; exec bash'" &

sleep 1

echo "[4/5] Starting CSI collector..."
lxterminal -e "bash -c 'cd ~/workspace/embedded && ./scripts/run_csi_raw_collector.sh; exec bash'" &

sleep 1

echo "[5/5] Starting synced frame builder..."
lxterminal -e "bash -c 'cd ~/workspace/embedded && ./scripts/run_synced_frame_builder.sh; exec bash'" &

echo "All services started."

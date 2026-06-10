#!/bin/bash

set -e

cd ~/workspace/embedded || exit 1

source .venv/bin/activate

for script in \
    scripts/setup_nexmon_csi_channel1.sh \
    scripts/run_csi_raw_collector.sh \
    scripts/run_synced_frame_builder.sh
do
    if [ ! -f "$script" ]; then
        echo "ERROR: $script not found"
        exit 1
    fi

    if [ ! -x "$script" ]; then
        echo "ERROR: $script is not executable"
        echo "Run: chmod +x $script"
        exit 1
    fi
done

echo "[0/6] Setting CSI channel..."
./scripts/setup_nexmon_csi_channel1.sh

sleep 2

echo "[1/6] Starting response_manager..."
lxterminal --title="response_manager" \
-e "bash -c 'cd ~/workspace/embedded && source .venv/bin/activate && python3 rpi_collector/response_manager.py; exec bash'" &

sleep 2

echo "[2/6] Starting analysis_bridge..."
lxterminal --title="analysis_bridge" \
-e "bash -c 'cd ~/workspace/embedded && source .venv/bin/activate && python3 rpi_collector/analysis_bridge.py; exec bash'" &

sleep 1

echo "[3/6] Starting main_loop..."
lxterminal --title="main_loop" \
-e "bash -c 'cd ~/workspace/embedded && source .venv/bin/activate && python3 rpi_collector/main_loop.py; exec bash'" &

sleep 1

echo "[4/6] Starting CSI collector..."
lxterminal --title="csi_collector" \
-e "bash -c 'cd ~/workspace/embedded && ./scripts/run_csi_raw_collector.sh; exec bash'" &

sleep 1

echo "[5/6] Starting synced frame builder..."
lxterminal --title="frame_builder" \
-e "bash -c 'cd ~/workspace/embedded && ./scripts/run_synced_frame_builder.sh; exec bash'" &

echo ""
echo "All services started."
echo ""
echo "For MQTT monitoring:"
echo "./debug.sh"
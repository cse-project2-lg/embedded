#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 rpi_collector/raw_mqtt_subscriber.py "$@"

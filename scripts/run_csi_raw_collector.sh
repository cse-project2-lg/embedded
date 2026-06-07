#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 rpi_collector/csi_raw_collector.py "$@"

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 rpi_collector/find_csi_raw_packet.py "$@"

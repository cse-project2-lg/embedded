#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 rpi_collector/publish_raw_example.py

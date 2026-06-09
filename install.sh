#!/bin/bash

echo "[1/4] Installing system packages..."

sudo apt update

sudo apt install -y \
    python3-venv \
    ffmpeg \
    portaudio19-dev \
    libportaudio2

echo "[2/4] Creating virtual environment..."

python3 -m venv venv

source venv/bin/activate

echo "[3/4] Installing Python packages..."

pip install --upgrade pip
pip install -r requirements.txt

echo "[4/4] Done."
echo "Activate with: source venv/bin/activate"
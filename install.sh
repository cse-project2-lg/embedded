#!/bin/bash

set -e

PROJECT_DIR="$HOME/workspace/embedded"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "프로젝트 디렉터리를 찾을 수 없습니다: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

echo "[1/4] Installing system packages..."

sudo apt update

sudo apt install -y \
    python3-venv \
    ffmpeg \
    portaudio19-dev \
    libportaudio2

echo "[2/4] Creating virtual environment..."

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
else
    echo ".venv already exists. Skipping creation."
fi

source .venv/bin/activate

echo "[3/4] Installing Python packages..."

if [ ! -f "requirements.txt" ]; then
    echo "requirements.txt를 찾을 수 없습니다."
    exit 1
fi

pip install --upgrade pip
pip install -r requirements.txt

echo "[4/4] Done."
echo ""
echo "설치가 완료되었습니다."
echo ""
echo "가상환경 활성화:"
echo "source ~/workspace/embedded/.venv/bin/activate"
# Raspberry Pi OS 및 기본 개발 환경 세팅

## 개요

본 문서는 Raspberry Pi 4 기반 Wi-Fi CSI 낙상 감지 시스템 개발을 위한 기본 개발 환경 구축 과정을 정리한다.

본 환경은 이후 CSI 데이터 수집, MQTT 기반 통신, PIR/ToF 센서 연동, 이벤트 생성 및 AI 분석 파이프라인 개발을 위한 기반 환경으로 사용된다.

---

## 개발 환경

### Hardware

* Raspberry Pi 4 Model B (8GB)

### Operating System

* Raspberry Pi OS 64-bit (Bookworm)

확인 명령어

```bash
cat /etc/os-release
```

---

## SSH 원격 접속 설정

### SSH 활성화

```bash
sudo raspi-config
```

선택

```text
Interface Options
 └── SSH
      └── Enable
```

상태 확인

```bash
sudo systemctl status ssh
```

---

## 시스템 업데이트

```bash
sudo apt update
sudo apt upgrade -y
```

---

## 개발 도구 설치

### Git

```bash
sudo apt install git -y
```

확인

```bash
git --version
```

### Python

```bash
python3 --version
```

Python 3.10 이상 사용

---

## Python 가상환경 구성

가상환경 생성

```bash
python3 -m venv .venv
```

활성화

```bash
source .venv/bin/activate
```

pip 업데이트

```bash
pip install --upgrade pip
```

---

## 필수 Python 패키지 설치

```bash
pip install -r requirements.txt
```

주요 패키지

* numpy
* scipy
* pandas
* paho-mqtt
* matplotlib
* pyserial
* smbus2
* RPi.GPIO
* scikit-learn
* jupyter
* psutil

---

## 시스템 의존성 설치

```bash
sudo apt install -y \
build-essential \
python3-dev \
libatlas-base-dev \
libopenblas-dev \
git \
cmake \
pkg-config
```

---

## CSI 및 센서 개발 대비 패키지 설치

```bash
sudo apt install -y \
tcpdump \
iw \
net-tools \
wireless-tools \
i2c-tools
```

설치 확인

```bash
iw dev
```

```bash
ifconfig
```

```bash
i2cdetect -y 1
```

---

## VSCode Remote SSH 연결

로컬 PC에서 VSCode 실행

필수 Extension

* Remote - SSH

SSH 접속 설정

```text
Host raspberrypi
    HostName <RASPBERRY_PI_IP>
    User <USERNAME>
```

접속

```text
Remote Explorer
 → raspberrypi
 → Connect
```

---

## Repository Clone

```bash
git clone <repository-url>
```

```bash
cd AI
```

---

## 설치 검증

### Python 실행 테스트

```bash
python3
```

```python
print("Hello Raspberry Pi")
```

### MQTT 패키지 확인

```python
import paho.mqtt.client as mqtt
```

### GPIO 패키지 확인

```python
import RPi.GPIO as GPIO
```

### I2C 확인

```bash
i2cdetect -y 1
```

---

## 결과

다음 항목이 정상 동작함을 확인하였다.

* Raspberry Pi OS 설치
* SSH 원격 접속
* Python 3.10 이상 실행
* Git 설치
* VSCode Remote SSH 연결
* Python 패키지 설치
* 시스템 의존성 설치
* 기본 Python 코드 실행
* CSI 및 센서 개발을 위한 사전 환경 구성

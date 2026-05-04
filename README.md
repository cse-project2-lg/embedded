# embeded
라즈베리파이 관련 코드


# Raspberry Pi Embedded Collector + MQTT Mock Pipeline

SRS 기준 FR-COL 데이터 수집/전처리, MQTT 연계, 로그/재현성 관리를 먼저 구현하기 위한 임베디드 코드입니다.

## 목표
- 회로 완성 전: Mock 데이터 또는 WiFall CSV 데이터로 MQTT 연동 테스트
- 회로 완성 후: `HardwareCollector`만 실제 센서 코드로 교체

## 전체 구조

embedded_edge_project/
├─ config/
│  └─ config.yaml
├─ data/
│  └─ sample_wifall.csv
├─ logs/
│  └─ .gitkeep
├─ src/
│  ├─ main.py
│  ├─ collectors/
│  │  ├─ base.py
│  │  ├─ mock_collector.py
│  │  ├─ wifall_collector.py
│  │  └─ hardware_collector.py
│  ├─ processing/
│  │  ├─ event_builder.py
│  │  └─ validator.py
│  ├─ mqtt/
│  │  └─ publisher.py
│  └─ utils/
│     ├─ config_loader.py
│     └─ logger.py
└─ requirements.txt


## 실행 환경
- Python 3.10+
- Mosquitto MQTT Broker
- Windows 테스트 가능


## 설치
pip install -r requirements.txt


라즈베리파이에서 Mosquitto 설치:
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto


## 실행
Mosquitto 실행:
cd "C:\Program Files\mosquitto"
.\mosquitto.exe -v


기본 Mock 실행:
python src/main.py --mode mock


WiFall CSV 기반 실행:
python src/main.py --mode wifall --wifall-csv data/sample_wifall.csv


실제 센서 연결 후 실행:
python src/main.py --mode hardware


## MQTT 수신 테스트
다른 터미널에서:
mosquitto_sub -h localhost -t "/sensor/#" -v
mosquitto_sub -h localhost -t "/event/#" -v


## 주요 토픽
- `/sensor/raw` : 센서 원시 데이터
- `/sensor/processed` : 검증/정제 후 데이터
- `/event/candidate` : 낙상 후보 이벤트
- `/system/status` : 시스템 상태
- `/system/error` : 오류 메시지

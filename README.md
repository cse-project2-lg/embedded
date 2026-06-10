# Release v0.2.0

## 🚀 주요 기능 추가

### Edge Logger (InfluxDB)

Edge 환경에서 수집되는 센서 및 WiFi CSI 데이터를 InfluxDB에 저장하는 데이터 로깅 파이프라인을 구현했습니다.

#### 주요 내용

* MQTT 기반 센서 데이터 수집
* WiFi CSI Raw 데이터 저장
* InfluxDB Batch Write 적용
* 센서 데이터 스키마 정합성 개선
* 데이터 유실 방지 및 재시도 로직 추가
* QoS=1 기반 MQTT 수신 안정성 향상
* InfluxDB 연결 검증(Ping/Bucket Check) 추가

---

### Voice Verification (STT)

AI 분석 결과만으로 즉시 보호자에게 알림을 전송하지 않고, 사용자 음성 응답을 통한 2차 확인 절차를 추가했습니다.

#### 주요 내용

* 음성 안내(MP3) 재생
* V829 마이크 기반 음성 입력
* Whisper STT 기반 한국어 음성 인식
* 사용자 응답 분류
* 응답 결과 기반 후속 처리

#### 사용자 확인 흐름

```text
AI Analysis
      │
      ▼
Voice Prompt
      │
      ▼
User Response
      │
      ▼
Whisper STT
      │
      ▼
Response Classification
      │
      ▼
Guardian Notification
```

---

### Edge Runtime Automation

Raspberry Pi 운영 편의성을 위한 자동화 스크립트를 추가했습니다.

#### 추가 스크립트

* install.sh
* run.sh
* debug.sh
* stop.sh

#### 지원 기능

* 환경 자동 구성
* 서비스 일괄 실행
* MQTT 토픽 모니터링
* 서비스 일괄 종료

---

## 🔧 안정성 개선

### MQTT

* 비동기 연결(connect_async) 적용
* 예외 처리 강화
* 연결 복구 안정성 향상

### InfluxDB

* 초기 연결 검증 추가
* Flush 재시도 로직 적용
* 데이터 유실 방지 강화

### Audio / STT

* Whisper Lazy Loading 적용
* Pygame Mixer Lazy Initialization 적용
* 오디오 장치 예외 처리 추가
* STT 실패 시 Fail-safe 처리 적용

---

## 📊 현재 파이프라인

```text
ESP32 Sensor + CSI
          │
          ▼
MQTT
          │
          ├── InfluxDB Logger
          │
          ▼
Preprocessing
          │
          ▼
Rule Engine
          │
          ▼
/event/candidate
          │
          ▼
AI Analysis
          │
          ▼
Voice Verification
          │
          ▼
Guardian Notification
```

---

## ✅ 포함된 기능

* Edge Logger
* InfluxDB Integration
* MQTT Pipeline
* Voice Verification
* Whisper STT
* V829 Microphone Support
* Runtime Automation Scripts
* MQTT Debug Monitoring
* Service Management Scripts

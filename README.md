# Edge Fall Detection Pipeline

## Overview

본 모듈은 Raspberry Pi Edge 환경에서 수집된 센서 데이터를 기반으로 낙상(Fall) 후보 이벤트를 탐지하는 역할을 수행한다.

ESP32에서 수집한 PIR, ToF 센서 데이터와 WiFi CSI 데이터를 전처리 및 동기화한 후, Sliding Window 기반 특징 추출과 Rule-Based 분석을 수행하여 낙상 후보 이벤트(`/event/candidate`)를 생성한다.

생성된 이벤트는 MQTT를 통해 Cloud AI 서버로 전달되며, 이후 AI/RAG 기반 2차 분석이 수행된다.

---

## Processing Flow

```text
ESP32 Sensor Data
        +
WiFi CSI Data
        │
        ▼
/preprocess/synced_frame
        │
        ▼
Preprocessor
        │
        ▼
Sliding Window Manager
        │
        ▼
Feature Extractor
        │
        ▼
Rule Engine
        │
        ▼
Event Candidate Generator
        │
        ▼
/event/candidate
        │
        ▼
Cloud AI Analysis
```

---

## 1. Preprocessing

### ToF Preprocessing

ToF(Time of Flight) 센서의 거리값을 정제한다.

수행 기능

* 센서 오류값(예: 8190) 제거
* 직전 유효 거리값으로 대체
* 거리 데이터 안정화

### CSI Preprocessing

WiFi CSI(Channel State Information) 데이터를 정제한다.

수행 기능

1. 복소수 CSI → 진폭(Amplitude) 변환
2. 서브캐리어 그룹핑
3. Z-Score 기반 이상치 제거
4. 동적 Baseline 제거
5. Butterworth Low-Pass Filter 적용

결과:

```python
csiFilteredAmp
```

---

## 2. Sliding Window Synchronization

전처리된 센서 데이터를 Timestamp 기반 Sliding Window로 관리한다.

### Window Configuration

| 항목          | 값  |
| ----------- | -- |
| Window Size | 7초 |
| Overlap     | 2초 |
| Step Size   | 5초 |

### 동작 방식

```text
Window #1
[0s ---------------- 7s]

Window #2
     [5s ---------------- 12s]

Window #3
          [10s ---------------- 17s]
```

각 Window는 다음 데이터를 포함한다.

```python
(
    csi_window,
    tof_window,
    pir_window,
    ts_window
)
```

---

## 3. Feature Extraction

각 Window에 대해 CSI, ToF, PIR 특징을 추출한다.

### CSI Features

| Feature         | Description   |
| --------------- | ------------- |
| csiMaxVariance  | 그룹별 최대 분산     |
| csiMaxAmplitude | 최대 진폭         |
| csiMaxDiff      | 인접 프레임 최대 변화량 |
| csiPacketCount  | CSI Packet 수  |

### ToF Features

| Feature            | Description |
| ------------------ | ----------- |
| tofMaxDrop         | 최대 거리 변화량   |
| tofCurrentDistance | 현재 거리       |
| tofStableMs        | 현재 위치 유지 시간 |

### PIR Features

| Feature           | Description      |
| ----------------- | ---------------- |
| pirAnyMotion      | 움직임 존재 여부        |
| pirSilentDuration | 마지막 움직임 이후 경과 시간 |

### Output

```python
{
    "csiMaxVariance": ...,
    "csiMaxAmplitude": ...,
    "csiMaxDiff": ...,
    "csiPacketCount": ...,

    "tofMaxDrop": ...,
    "tofCurrentDistance": ...,
    "tofStableMs": ...,

    "pirAnyMotion": ...,
    "pirSilentDuration": ...
}
```

---

## 4. Rule-Based Detection

Window 특징을 기반으로 1차 낙상 후보 판정을 수행한다.

### Detection Rules

#### CSI Rule

CSI 변화량이 임계값 이상인 경우

```python
csiMaxDiff >= CSI_DIFF_THRESHOLD
```

#### ToF Rule

거리 변화량이 임계값 이상인 경우

```python
tofMaxDrop >= TOF_DROP_THRESHOLD
```

#### PIR Rule

일정 시간 이상 움직임이 없는 경우

```python
pirSilentDuration >= PIR_SILENT_THRESHOLD_MS
```

---

### Score Calculation

| Rule      | Score |
| --------- | ----- |
| CSI 변화 감지 | +0.3  |
| ToF 거리 급변 | +0.4  |
| PIR 정지 지속 | +0.3  |

최대 점수

```python
1.0
```

---

### Risk Level

| Score | Risk Level |
| ----- | ---------- |
| ≥ 0.8 | HIGH       |
| ≥ 0.5 | MEDIUM     |
| < 0.5 | LOW        |

---

## 5. Event Candidate Generation

HIGH 또는 MEDIUM 위험도가 탐지되면 `/event/candidate` 이벤트를 생성한다.

### Event Structure

```json
{
  "type": "event.candidate",
  "eventId": "EVT-20260606-0001",
  "timestamp": "2026-06-06T15:42:10.123+09:00",

  "deviceId": "RPi4-001",
  "roomId": "living-room",

  "window": {
    "startMonotonicNs": 123456789000,
    "endMonotonicNs": 124456789000,
    "durationMs": 7000
  },

  "sensorSummary": {
    "pirMotion": false,
    "pirLastMotionMs": 2400,

    "tofDistanceMm": 1820,
    "tofChangeMm": 680,
    "tofStableMs": 2100,

    "csi": {
      "status": "AVAILABLE",
      "changeScore": 0.82,
      "packetCount": 57
    }
  },

  "localScore": 0.86,
  "localRiskLevel": "HIGH",

  "candidateReason": [
    "CSI 급격 변화",
    "ToF 거리 급변",
    "움직임 정지 지속"
  ]
}
```

---

## 6. MQTT Integration

### Subscribe

```text
/preprocess/synced_frame
```

동기화 및 전처리 완료 데이터 수신

### Publish

```text
/event/candidate
```

낙상 후보 이벤트 발행

### Next Stage

```text
/event/candidate
        │
        ▼
analysis_bridge.py
        │
        ▼
AI/RAG Server
        │
        ▼
/analysis/result
```

Cloud AI가 2차 분석을 수행하며, 최종 낙상 여부 판단은 AI 분석 결과를 기반으로 결정된다.

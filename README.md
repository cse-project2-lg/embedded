# 📡 Wi-Fi CSI 및 멀티 센서 기반 엣지 낙상 감지 시스템 (Edge Fall Detection System)

본 시스템은 Raspberry Pi 4 환경에서 복합 비접촉 센서 데이터인 Wi-Fi CSI(Channel State Information), ToF(Time-of-Flight) 거리 데이터, PIR(Passive Infrared) 이지 영역 움직임 신호를 실시간 융합 및 전처리하여 사용자의 낙상 사고를 감지하는 **엣지 컴퓨팅 기반 실시간 데이터 파이프라인 및 감지 시스템**입니다.

시스템은 데이터 융합, 신호 처리 필터 뱅크, 실시간 슬라이딩 윈도우 관리, 가중치 기반 룰 엔진, 클라우드 AI 정밀 분석 연동 브릿지, 그리고 실시간 음성 응답 상태 머신(State Machine)을 포함하는 엔드투엔드 구조로 설계되었습니다.

---

## 🏗️ 전체 시스템 아키텍처 및 데이터 흐름

엣지 파이프라인 내 전 단계는 MQTT 브로커를 중심 축으로 상호 독립적인 프로세스로 동작하며, 병목 현상을 방지하기 위해 입출력 큐(Queue)와 논블로킹(Non-blocking) 스레드 풀을 활용합니다.

```text
 [ESP32 Sensor Node] --------> MQTT (/sensor/raw) -------> [synced_frame_builder]
                                                                  ^
 [Nexmon CSI wlan0]  -> UDP -> MQTT (/csi/raw) ----------> -------+
                                                                  |
                                                           [synced_frame]
                                                                  |
                                                                  v
 [analysis_bridge]  <-- MQTT (/event/candidate) <------ [main_loop.py]
         |                                           (Filter, Window, Rule Engine)
     REST API (Post)
         v
 [Cloud AI/RAG Server]
         |
     REST Response
         v
 [analysis_bridge]  --------> MQTT (/analysis/result) ---> [response_manager]
                                                                  |
                                                       [LOCAL MP3 / Whisper STT]
                                                                  |
                                                            REST API (Post)
                                                                  v
                                                       [Cloud Notification Service]
                                                       (보호자 알림: KAKAO, SMS)

```

---

## 🔬 핵심 모듈별 전처리 및 알고리즘 상세 스펙

### 1. 데이터 수집 및 물리 계층 바인딩 (`csi_raw_collector.py`)

* **소켓 버퍼 최적화**: 고주파수 CSI 버스트 패킷 유실을 방지하기 위해 커널 수신 버퍼 크기를 `4MB`(`4 * 1024 * 1024` bytes)로 확장하여 소켓을 바인딩합니다.
* **세션 관리**: 수집기 재시작 시 시퀀스 넘버(`seq`)가 초기화되더라도 패킷 ID의 고유성을 보장하기 위해 타임스탬프와 프로세스 ID(PID)를 조합한 `COLLECTOR_SESSION_ID`를 기반으로 `packetId`를 난수화합니다.
* **디스크 I/O 병목 제거**: 일자별 고속 JSONL 로그 기록 시 패킷마다 파일을 열고 닫는 오버헤드를 방지하기 위해, 파일 핸들을 내부 캐시에 유지하고 날짜 변경 시에만 갱신하는 파일 스트림 관리 기법을 적용했습니다.

### 2. 시계열 시간 동기화 엔진 (`synced_frame_builder.py`)

* **센서 트리거링 융합**: ESP32의 타임스탬프 부재 문제를 해결하기 위해, 라즈베리파이의 단조 시계(Monotonic Clock) 수신 나노초(`mqttReceivedMonotonicNs`)를 기준 축으로 정렬합니다.
* **정렬 프레임 규칙**: `/sensor/raw` 메시지 1개가 수신될 때마다 동기화 프레임이 생성됩니다. 직전 센서 패킷 수신 시점부터 현재 수신 시점 사이에 도달한 모든 CSI 패킷 참조자(`csiRawRefs`)를 해당 프레임에 종속 바인딩합니다.
* **메모리 Pruning 기법**: 무한 루프에서 큐가 비대해지는 현상을 막기 위해 `SYNC_CSI_RETENTION_MS` (기본값: 5000ms) 기준을 초과한 오래된 CSI 레코드는 락(Lock)을 획득하여 버퍼에서 즉시 배제(`popleft`)합니다.

### 3. 신호 전처리 필터 뱅크 (`preprocessor.py`)

* **Nexmon CSI 페이로드 파싱**: Base64 디코딩 후 18바이트의 고정 헤더(Magic Number, RSSI 등)를 오프셋 처리하고, 이후 데이터를 Little-Endian 포맷의 16비트 정수 배열(`<h`)로 언팩하여 복소수($\text{Real} + 1j \times \text{Imag}$) 배열을 복원합니다.
* **CSI 5단계 정제 알고리즘**:
1. **진폭 추출**: 복소 신호의 절대값($|H(f)|$) 계산
2. **서브캐리어 그룹핑**: 총 64개 서브캐리어를 `group_size=4` 단위로 평균화하여 16개의 대표 그룹 채널로 압축
3. **Z-Score 아웃라이어 클리핑**: 채널별 평균 및 표준편차($\sigma$)를 산출하여 $\pm3\sigma$ 범위를 벗어나는 이상 진폭을 상하한선으로 클리핑
4. **동적 Baseline 제거**: 지수 이동 평균(EMA, 계수 $\alpha=0.05$)을 활용하여 정적 환경 노이즈 및 가구 배치 등으로 인한 직류(DC) 바이어스 성분을 실시간 추적 및 감산
5. **상태 유지 Butterworth LPF**: 샘플링 주파수 $f_s = 100\text{Hz}$, 차단 주파수 $f_c = 10\text{Hz}$ 조건의 4차 저역통과 필터를 구현하되, 불연속 청크 연산 시 신호 왜곡을 방지하기 위해 필터 지연 상태(`zi`)를 인스턴스 변수에 보존 및 계승 (`scipy.signal.lfilter` 활용)


* **ToF 노이즈 정제**: 거리가 최대 에러값(`8190mm`) 이상이거나 `tofValid=False`, `tofError=True`, `tofTimeout=True`인 불량 프레임 감지 시, 신호 단절 대신 직전의 정상 유효 거리값(`last_valid`)으로 보간 대체합니다.

### 4. 슬라이딩 윈도우 관리자 (`window_manager.py`)

* **시계열 윈도우 정의**: 실시간 데이터 스트림 상에서 낙상 행동 패턴의 전조-발생-후속 단계를 포착하기 위해 타임스탬프 기반 윈도우를 제어합니다.
* 윈도우 크기 (`WINDOW_SIZE_SEC`): `7초` (`7,000,000,000` 나노초)
* 오버랩 크기 (`OVERLAP_SEC`): `2초`
* 슬라이드 스텝 (`STEP_SIZE_NS`): `5초` 마다 다음 윈도우로 이동
* 최소 샘플 제한 (`MIN_WINDOW_SAMPLES`): 윈도우 내 최소 `5개` 이상의 유효 데이터 세트가 확보되어야 연산을 수행합니다.



### 5. 특징 추출 엔진 (`feature_extractor.py`)

* **CSI 특징 추출**:
* `csiMaxVariance`: 윈도우 내 융합된 시간축 배열에서 채널별 분산($\text{Var}$)의 최대값 추적
* `csiMaxDiff`: 연속된 CSI 프레임 간 차분 배열의 절대값 중 최대값($\max |\Delta \text{Amp}|$)으로 급격한 위상/진폭 변동 포착


* **ToF 특징 추출**:
* `tofMaxDrop`: 순차 프레임 간 거리 차이($arr[i] - arr[i+1]$) 중 최대 양수 변화량으로, 수직 낙하 시 발생하는 급격한 거리 감소 측정
* `tofStableMs`: 바닥에 떨어진 후 안정화 상태를 인지하기 위해, 현재 최신 거리값 기준 $\pm50\text{mm}$ 임계치 이내를 유지하는 지속 시간을 나노초 시계로 역산 처리


* **PIR 특징 추출**:
* `pirSilentDuration`: 낙상 후 의식 상실 상태를 모니터링하기 위해, 윈도우 내에서 마지막으로 `pirMotion=True`(움직임 발생)가 관측된 시점부터 현재 윈도우 종단점까지의 침묵 시간($\text{ms}$) 계산



### 6. 가중치 기반 룰 엔진 (`rule_engine.py`)

가상 위험 지수(Local Score)는 총합 1.0 만점의 가중치 결합 모델로 판단하며, 수치 예외 처리(NaN, Infinite, Boolean 입력 차단) 파이프라인이 엄격하게 적용되어 있습니다.

$$\text{Local Score} = (\text{CSI Trigger} \times 0.3) + (\text{ToF Trigger} \times 0.4) + (\text{PIR Trigger} \times 0.3)$$

| 평가 대상 특징 | 가중치 | 활성화 임계치 (Threshold) | 판정 사유 (`candidateReason`) |
| --- | --- | --- | --- |
| `csiMaxDiff` | **0.3** | $\ge 1.0$ | `"CSI 급격 변화"` |
| `tofMaxDrop` | **0.4** | $\ge 500\text{mm}$ | `"ToF 거리 급변"` |
| `pirSilentDuration` | **0.3** | $\ge 2000\text{ms}$ | `"움직임 정지 지속"` |

* **위험도 등급 분류 (`localRiskLevel`)**:
* $\text{Score} \ge 0.8$: **HIGH**
* $0.5 \le \text{Score} < 0.8$: **MEDIUM**
* $\text{Score} < 0.5$: **LOW** (파이프라인에서 즉시 Drop 처리 및 Skip)



---

## 📋 데이터 통신 규격 (Data Contracts)

### 1. `/event/candidate` 메시지 구조 (`main_loop.py` -> `analysis_bridge.py`)

룰 엔진이 예외 상황(MEDIUM 이상)으로 판정한 고유 낙상 이벤트 스펙입니다.

```json
{
  "type": "event.candidate",
  "eventId": "EVT-20260624-0001",
  "timestamp": "2026-06-24T23:25:00.123+09:00",
  "deviceId": "RPi4-001",
  "roomId": "living-room",
  "window": {
    "startMonotonicNs": 123456789000,
    "endMonotonicNs": 130456789000,
    "durationMs": 7000.0
  },
  "sensorSummary": {
    "pirMotion": false,
    "pirLastMotionMs": 2450.0,
    "tofDistanceMm": 450.0,
    "tofChangeMm": 680.0,
    "tofStableMs": 2100.0,
    "csi": {
      "status": "AVAILABLE",
      "changeScore": 0.82,
      "packetCount": 150
    }
  },
  "localScore": 0.70,
  "localRiskLevel": "MEDIUM",
  "candidateReason": ["CSI 급격 변화", "ToF 거리 급변"]
}

```

### 2. `/analysis/result` 메시지 구조 (`analysis_bridge.py` -> `response_manager.py`)

클라우드 AI/RAG 서버가 분석 결과를 반환하거나 REST 실패 시 엣지 자체에서 Fallback 처리한 수신 프로토콜 규격입니다.

```json
{
  "type": "analysis.result",
  "eventId": "EVT-20260624-0001",
  "timestamp": "2026-06-24T23:25:02.456+09:00",
  "isFall": true,
  "confidence": 0.88,
  "riskLevel": "HIGH",
  "recommendedAction": "VERIFY_USER",
  "situationSummary": "신호 패턴 분석 결과 수직 낙하 후 움직임 정지가 식별되어 사용자 확인 절차를 개시합니다.",
  "analysisReason": "ToF 급감 신호와 고주파 CSI 스펙트럼 변동이 낙상 동적 특성과 일치함",
  "verificationPlan": {
    "required": true,
    "method": "LOCAL_MP3_STT",
    "promptAsset": "are_you_ok_ko.mp3",
    "expectedOkText": ["네"],
    "timeoutSec": 10
  },
  "analysisStatus": "SUCCESS"
}

```

---

## 🚦 상태 머신 기반 예외 에스컬레이션 규격

`response_manager.py`는 AI의 분석서(`recommendedAction`)에 명시된 행동 계획에 따라 음성 인터랙션 및 상황 전파를 동적으로 제어합니다.

### 1. 사용자 음성 분류 규칙 (`classify_user_response`)

Whisper STT를 거쳐 수신된 텍스트는 정규식 정문화(공백, 특수문자 제거 및 소문자화)를 거친 후 4가지 상태 체계로 분류됩니다.

* **`OK`**: 정상 생존 반응 상태.
* 매칭 키워드: `verificationPlan.expectedOkText` (기본값: `["네"]`). 파이프라인이 즉시 종료되며 시스템은 정상 닫힘(`VERIFIED_OK_CLOSED`) 상태로 복귀합니다.


* **`HELP`**: 음성 구조 요청 상태.
* 매칭 키워드: `["도와줘", "살려줘", "119", "구해줘", "응급", "위험"]`. 예외없이 즉시 보호자 최고 등급 알림을 발송합니다.


* **`NOT_OK`**: 신체 이상 표출 상태.
* 매칭 키워드: `["아파", "못 일어나", "아니", "괜찮지 않아", "안 괜찮"]`. 즉시 보호자 에스컬레이션을 트리거합니다.


* **`NO_RESPONSE` / `UNCLEAR**`: 의식 상실 유의 상태.
* 지정된 제한 시간(`timeoutSec`, 기본 10초) 내 음성이 들어오지 않거나 판독이 불가할 경우 보호자에게 즉시 긴급 알림을 전송합니다.



### 2. 에스컬레이션 사유 매핑 스펙

보호자 알림 서비스로 Request를 전송할 때, 사용자 반응에 따라 클라우드 관제 웹에 기록될 `escalationReason`이 자동으로 분기 처리됩니다.

| 인터랙션 결과 (`userResponse`) | 발생한 구체적 에스컬레이션 사유 (`escalationReason`) |
| --- | --- |
| **`HELP`** | `"사용자 음성에서 도움 요청 표현이 감지되었습니다."` |
| **`NOT_OK`** | `"사용자 음성에서 이상 상태 또는 부정 응답이 감지되었습니다."` |
| **`NO_RESPONSE`** | `"사용자 확인 질문 후 응답 제한 시간 내 음성 응답이 수신되지 않았습니다."` |
| **`UNCLEAR`** | `"STT 결과가 불명확하여 정상 응답으로 판단할 수 없습니다."` |

---

## 🛠️ 상세 환경 변수 매핑 테이블 (`.env`)

시스템 구성에 필요한 핵심 파라미터 리스트입니다. 루트 디렉토리에 파일 형태로 배치하여 가동합니다.

| 환경 변수명 | 기본값 | 데이터 타입 | 상세 기능 설명 |
| --- | --- | --- | --- |
| `MQTT_HOST` | `127.0.0.1` | String | 로컬 엣지 통신용 MQTT 브로커 IP 주소 |
| `MQTT_PORT` | `1883` | Integer | MQTT 통신 바인딩 포트 |
| `CSI_UDP_PORT` | `5500` | Integer | Nexmon CSI 드라이버가 패킷을 포워딩하는 UDP 포트 |
| `AI_ANALYZE_URL` | `http://127.0.0.1:8000/...` | String | AI/RAG 정밀 분석용 클라우드 REST 엔드포인트 |
| `NOTIFICATION_REQUEST_URL` | `http://127.0.0.1:8000/...` | String | 카카오톡/SMS 전송용 알림 서비스 엔드포인트 |
| `SYNC_CSI_LOOKBACK_MS` | `100` | Integer | 초기 융합 프레임 빌드 시 역산할 CSI 타임라인 탐색 범위 |
| `SYNC_FRAME_EMIT_DELAY_MS` | `50` | Integer | MQTT 순서 뒤바뀜(Jitter) 보정을 위한 프레임 지연 방출 시간 |
| `SYNC_CSI_RETENTION_MS` | `5000` | Integer | 링 버퍼 내 CSI 패킷 보존 한도 나노초 변환 기준점 |
| `STUB_STT_TRANSCRIPT` | `""` | String | 테스트 환경 구동 시 하드코딩 마이크 입력을 대체할 Stub 변수 |

---

## 🚀 단계별 생산 가동 지침

시스템의 유기적 흐름 제어를 위해 각 백그라운드 데몬 및 스크립트는 반드시 다음 시퀀스 순서대로 실행해야 합니다.

### 1단계: 라디오 및 RF 커널 패치 활성화

네트워크 인터페이스 카드(`wlan0`)를 모니터 모드로 전환하고 CSI 수집 서브 서킷을 채널 1, 대역폭 20MHz로 락킹합니다.

```bash
chmod +x ./scripts/setup_nexmon_csi_channel1.sh
sudo ./scripts/setup_nexmon_csi_channel1.sh

```

### 2단계: 네트워크 인그레스 디바이스 가동

커널 단 UDP 포트 백그라운드 리스너를 실행하여 입출력 스트림을 가동하고 고속 실시간 파일 디스크 로깅을 개시합니다.

```bash
./scripts/run_csi_raw_collector.sh

```

### 3단계: 나노초 정렬 융합 엔진 구동

서로 다른 소스 기기(ESP32, RPi4) 채널의 분산 원격 패킷들을 공통 타임스탬프 큐 구조로 동기화 바인딩하기 위해 프레임 엔진을 개시합니다.

```bash
./scripts/run_synced_frame_builder.sh

```

### 4단계: 실시간 데이터 파이프라인 및 코어 가동 (Main)

전처리, 슬라이딩 윈도우 버퍼링, 특징 추출, 룰 기반 실시간 추론 스레드를 실행하여 이벤트 필터링 연산을 본격적으로 수행합니다.

```bash
python3 rpi_collector/main_loop.py

```

### 5단계: 상위 레이어 통신 인프라 브릿지 기동

이벤트 발생 시 클라우드로 즉각 전파하기 위한 HTTP 통신 소켓 멀티스레드 인스턴스들을 활성화합니다.

```bash
# 터미널 A: AI 웹 브릿지 가동
python3 rpi_collector/analysis_bridge.py

# 터미널 B: 로컬 오디오 입출력 상태 오토마타 가동
python3 rpi_collector/response_manager.py

```

---

## 🧪 장애 극복 및 Failover 정책

* **네트워크 단절 및 AI 응답 불가 시 (`FALLBACK_RULE`)**:
* 클라우드 AI 서버가 500 에러를 반환하거나 타임아웃(`REQUEST_TIMEOUT_SEC=30`)이 발생하면 `analysis_bridge.py`에서 즉시 자체적인 예외 복구 알고리즘이 발동합니다.
* 이 경우 신뢰도 점수 `0.6`, 위험도 `MEDIUM` 수준의 규격화된 `FALLBACK_RULE` 결과를 강제 구성하여 파이프라인에 주입합니다. 이를 통해 서버가 다운되더라도 라즈베리파이 단독으로 로컬 음성 질문 스피커를 송출하여 사용자의 생존 유무를 끝까지 판단할 수 있도록 안정성을 확보했습니다.


* **Wi-Fi 트래픽 단절 시 대처**:
* ESP32와 공유기 간 무선 연결 부실로 인해 무선 패킷 손실이 확인되면 (`pingOk=False`), CSI 전처리 모듈은 유효하지 않은 반사파 데이터로 오판하지 않도록 즉시 해당 프레임의 CSI 분석 처리를 스킵하고 ToF와 PIR 분석 전용 모드로 하향 전환하여 감지를 지속합니다.

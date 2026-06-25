# ESP32 Sensor Hub

## Overview

본 모듈은 ESP32 기반 센서 허브로, PIR 센서와 ToF(VL53L1X) 센서를 이용하여 환경 데이터를 수집하고 MQTT를 통해 Raspberry Pi Edge 서버로 전송하는 역할을 수행한다. 또한 Raspberry Pi에서 Wi-Fi CSI(Channel State Information)를 수집할 수 있도록 AP를 대상으로 지속적인 ICMP Ping 트래픽을 생성한다.

ESP32는 센서 데이터의 단순 수집 및 전송만 수행하며, 센서 데이터와 Wi-Fi CSI의 시간 동기화, 멀티모달 데이터 융합 및 낙상 이벤트 분석은 Raspberry Pi에서 수행한다.

---

## Features

* PIR(Motion) 센서 데이터 수집
* VL53L1X ToF 거리 센서 데이터 수집
* Wi-Fi Ping 기반 CSI 트래픽 생성
* MQTT 기반 `/sensor/raw` 데이터 전송
* JSON 형식 센서 데이터 직렬화
* 실시간 Serial Monitor 디버깅 지원
* Wi-Fi 및 MQTT 자동 재연결

---

## Hardware Configuration

| Device  | ESP32 Pin |
| ------- | --------- |
| PIR OUT | GPIO27    |
| ToF SDA | GPIO21    |
| ToF SCL | GPIO22    |

---

## Software Stack

* ESP32 Arduino Framework
* PubSubClient
* ArduinoJson
* VL53L1X
* ESP32Ping

---

## Data Flow

```text
PIR Sensor
            \
             \
              --> ESP32 --> MQTT (/sensor/raw) --> Raspberry Pi
             /
ToF Sensor  /

ESP32
   |
   +--> ICMP Ping --> AP
                      |
                      +--> Raspberry Pi CSI Capture
```

---

## MQTT Topic

### Publish

```
/sensor/raw
```

---

## Example Payload

```json
{
  "type": "sensor.raw",
  "source": "esp32_sensor_node",
  "deviceId": "ESP32-001",
  "seq": 125,
  "sampleIntervalMs": 100,
  "sensors": {
    "pirMotion": false,
    "pirValue": 0,
    "tofDistanceMm": 1542,
    "tofValid": true,
    "tofTimeout": false,
    "tofError": null
  },
  "transport": {
    "wifiRssiDbm": -47,
    "pingOk": true
  }
}
```

---

## Configuration

프로젝트에서 사용하는 네트워크 정보는 `config.h`를 통해 설정한다.

```cpp
#define WIFI_SSID "rasberrypi"
#define WIFI_PASSWORD "wisasy23"

#define AP_IP "192.168.137.1"

#define MQTT_HOST "192.168.137.19"
#define MQTT_PORT 1883
```

| Parameter     | Description              |
| ------------- | ------------------------ |
| WIFI_SSID     | Wi-Fi SSID               |
| WIFI_PASSWORD | Wi-Fi Password           |
| AP_IP         | Ping 대상 AP(Gateway) 주소   |
| MQTT_HOST     | Raspberry Pi MQTT Broker |
| MQTT_PORT     | MQTT Broker Port         |

---

## Serial Monitor

센서 상태와 MQTT 전송 결과는 Arduino Serial Monitor(115200 baud)를 통해 실시간으로 확인할 수 있다.

예시

```text
WiFi connected.
TOF OK
SYSTEM READY

MQTT PUB OK:
{
  ...
}
```

---

## Notes

* ESP32는 센서 원본(Raw) 데이터만 전송한다.
* 센서 데이터의 Timestamp는 Raspberry Pi 수신 시점을 기준으로 생성된다.
* Wi-Fi CSI 데이터와 PIR/ToF 데이터의 시간 동기화는 Raspberry Pi Edge에서 수행된다.
* Ping 패킷은 Wi-Fi CSI 수집을 위한 무선 트래픽 생성 용도로만 사용된다.

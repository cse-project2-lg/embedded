// ESP32 Sensor Hub & CSI Traffic Generator
// - PIR Sensor
// - Single ToF Sensor (VL53L1X)
// - WiFi CSI Traffic Generation
// - UART JSON Streaming

#include <WiFi.h>
#include <ESP32Ping.h>

#include <Wire.h>
#include <VL53L1X.h>

#include <ArduinoJson.h>

// WiFi 설정
const char* ssid = "iptime";
const char* password = "12345678";
const char* AP_IP = "192.168.0.1";

// PIN 설정
#define PIR_PIN 27

// ToF 객체
VL53L1X tofSensor;

// 전역 변수
int prevDistance = -1;

// WiFi 연결
void setupWiFi() {
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
    }
    Serial.println("WIFI OK");
}

// ToF 초기화

void setupToF() {
    tofSensor.setTimeout(500);

    // ToF 초기화 실패 시 정지
    if (!tofSensor.init()) {
        Serial.println("TOF FAIL");
        while (1) {
            delay(10);
        }
    }

    // 연속 거리 측정 시작
    tofSensor.startContinuous(50);
    Serial.println("TOF OK");
}

// setup()
void setup() {
    // UART 시작
    Serial.begin(115200);
    delay(2000);
    Serial.println("BOOT");

    // I2C 시작
    // SDA = GPIO21
    // SCL = GPIO22

    Wire.begin(21, 22);

    // I2C 속도
    Wire.setClock(100000);

    // PIR 설정

    // INPUT_PULLDOWN 중요
    // PIR 없을 때 LOW 유지
    pinMode(PIR_PIN, INPUT_PULLDOWN);

    // WiFi 연결
    setupWiFi();

    // ToF 초기화
    setupToF();

    Serial.println("SYSTEM READY");
}

// loop()
void loop() {

    // CSI용 Ping 전송
    IPAddress targetIP;
    targetIP.fromString(AP_IP);

    // Ping 실행
    bool pingResult =
        Ping.ping(targetIP, 1);

    // 1초마다 Ping 상태 출력

    static unsigned long lastPingPrint = 0;
    if (millis() - lastPingPrint > 1000) {
        lastPingPrint = millis();
        if (pingResult) {
            Serial.println(
                "!!!! PING OK !!!!"
            );

        } else {
            Serial.println(
                "XXXX PING FAIL XXXX"
            );
        }
    }

    // ToF 거리 읽기
    int distance = tofSensor.read();

    // timeout 체크
    if (tofSensor.timeoutOccurred()) {
        Serial.println("TOF TIMEOUT");
    }

    // PIR 읽기

    // 움직임 없으면 0
    // 움직임 감지 시 1

    bool motion =
        digitalRead(PIR_PIN);

    // 급격한 거리 감소 감지

    bool suddenDrop = false;
    if (prevDistance > 0 &&
        distance > 0) {

        int diff =
            prevDistance - distance;

        // 700mm 이상 감소 시

        if (diff > 700) {
            suddenDrop = true;
        }
    }

    // 현재 거리 저장
    prevDistance = distance;

    // 낙상 후보 판단

    bool fallCandidate = false;
    if (motion && suddenDrop) {
        fallCandidate = true;
    }

    // JSON 생성
    StaticJsonDocument<512> doc;

    doc["deviceId"] =
        "esp32_sensor_hub";

    doc["timestamp"] =
        millis();

    // 센서 데이터

    JsonObject sensors =
        doc.createNestedObject("sensors");

    sensors["pir_motion"] =
        motion;

    sensors["tof_distance_mm"] =
        distance;

    // 분석 데이터

    JsonObject analysis =
        doc.createNestedObject("analysis");

    analysis["sudden_drop"] =
        suddenDrop;

    analysis["fall_candidate"] =
        fallCandidate;

    // UART JSON 출력

    serializeJson(doc, Serial);
    Serial.println();

    // 디버그 출력

    Serial.print("Distance(mm): ");
    Serial.println(distance);
    Serial.print("Motion: ");
    Serial.println(motion);
    Serial.print("SuddenDrop: ");
    Serial.println(suddenDrop);
    Serial.print("FallCandidate: ");
    Serial.println(fallCandidate);
    Serial.println("----------------------");


    // 100ms 주기
    delay(100);
}
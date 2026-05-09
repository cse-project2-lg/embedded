#include <Wire.h>
#include <VL53L0X.h>

const int PIR_PIN = 27;
VL53L0X tofSensor;

void setup() {
  Serial.begin(115200);

  pinMode(PIR_PIN, INPUT);

  Wire.begin(); // ESP32 기본 I2C 핀: SDA(21), SCL(22)

  tofSensor.setTimeout(500);
  if (!tofSensor.init()) {
    Serial.println("Failed to detect and initialize ToF sensor!");
    while (1) {}
  }

  tofSensor.startContinuous();
  
  Serial.println("System Initialized. Starting data collection...");
}

void loop() {
  // 1. PIR 센서 값 읽기 (HIGH/LOW)
  int pirState = digitalRead(PIR_PIN);

  // 2. ToF 센서 값 읽기 (거리, mm 단위)
  uint16_t distance = tofSensor.readRangeContinuousMillimeters();

  // 3. ToF 센서 에러 처리 (타임아웃 등)
  if (tofSensor.timeoutOccurred()) {
    Serial.print(" ToF TIMEOUT");
    distance = 0; // 에러 시 0 또는 특정 값으로 처리
  }

  // 4. 데이터 포맷팅 및 시리얼 전송
  Serial.print(pirState);
  Serial.print(",");
  Serial.println(distance);

  delay(100); 
}
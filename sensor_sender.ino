// ESP32 Sensor Hub
// - PIR Sensor
// - Single ToF Sensor (VL53L1X)
// - Wi-Fi CSI traffic generation by Ping
// - MQTT publish: /sensor/raw
// Required Arduino libraries:
// - PubSubClient
// - ArduinoJson
// - VL53L1X
// - ESP32Ping

#include <WiFi.h>
#include <PubSubClient.h>
#include <ESP32Ping.h>

#include <Wire.h>
#include <VL53L1X.h>
#include <ArduinoJson.h>

// Wi-Fi / MQTT settings
const char* WIFI_SSID = "iptime";
const char* WIFI_PASSWORD = "12345678";

// AP address used only for generating Wi-Fi traffic for CSI capture.
const char* AP_IP = "192.168.0.1";

// Raspberry Pi or local MQTT broker address.
// Change this to your RPi MQTT broker IP.
const char* MQTT_HOST = "192.168.0.100";
const uint16_t MQTT_PORT = 1883;

const char* DEVICE_ID = "ESP32-001";
const char* MQTT_CLIENT_ID = "esp32-sensor-node";
const char* TOPIC_SENSOR_RAW = "/sensor/raw";

// =============================
// Pin / sampling settings
// =============================
#define PIR_PIN 27

const uint32_t SAMPLE_INTERVAL_MS = 100;  // 10Hz PIR/ToF raw sample
const uint32_t WIFI_RECONNECT_DELAY_MS = 1000;
const uint32_t MQTT_RECONNECT_DELAY_MS = 1000;

// =============================
// Global objects
// =============================
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
VL53L1X tofSensor;

uint32_t seq = 0;
uint32_t lastSampleAt = 0;
uint32_t lastWiFiReconnectAt = 0;
uint32_t lastMqttReconnectAt = 0;

void setupWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("WiFi connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("WiFi connected. IP=");
  Serial.println(WiFi.localIP());
}

void ensureWiFiConnected() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  uint32_t now = millis();
  if (now - lastWiFiReconnectAt < WIFI_RECONNECT_DELAY_MS) {
    return;
  }

  lastWiFiReconnectAt = now;
  Serial.println("WiFi reconnecting...");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void setupMqtt() {
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  mqttClient.setBufferSize(512);
}

void ensureMqttConnected() {
  if (mqttClient.connected()) {
    return;
  }

  uint32_t now = millis();
  if (now - lastMqttReconnectAt < MQTT_RECONNECT_DELAY_MS) {
    return;
  }

  lastMqttReconnectAt = now;
  Serial.print("MQTT connecting...");

  if (mqttClient.connect(MQTT_CLIENT_ID)) {
    Serial.println("OK");
  } else {
    Serial.print("FAILED, rc=");
    Serial.println(mqttClient.state());
  }
}

void setupToF() {
  tofSensor.setTimeout(500);

  if (!tofSensor.init()) {
    Serial.println("TOF INIT FAIL");
    while (1) {
      delay(10);
    }
  }

  tofSensor.startContinuous(50);
  Serial.println("TOF OK");
}

bool generateCsiTraffic() {
  IPAddress targetIP;
  targetIP.fromString(AP_IP);

  // This ping exists only to generate Wi-Fi packets.
  // CSI itself is captured by Raspberry Pi / Nexmon, not by this MQTT JSON.
  return Ping.ping(targetIP, 1);
}

void publishSensorRaw() {
  bool pingOk = generateCsiTraffic();

  bool pirMotion = digitalRead(PIR_PIN) == HIGH;

  int distance = tofSensor.read();
  bool tofTimeout = tofSensor.timeoutOccurred();

  // VL53L1X invalid/error values can vary by library/hardware state.
  // Keep raw validity explicit so RPi can decide how to handle it later.
  bool tofValid = (!tofTimeout && distance > 0 && distance < 8190);

  StaticJsonDocument<512> doc;

  doc["type"] = "sensor.raw";
  doc["source"] = "esp32_sensor_node";
  doc["deviceId"] = DEVICE_ID;
  doc["seq"] = seq++;
  doc["sampleIntervalMs"] = SAMPLE_INTERVAL_MS;

  JsonObject sensors = doc.createNestedObject("sensors");
  sensors["pirMotion"] = pirMotion;
  sensors["pirValue"] = pirMotion ? 1 : 0;

  if (tofValid) {
    sensors["tofDistanceMm"] = distance;
    sensors["tofError"] = nullptr;
  } else {
    sensors["tofDistanceMm"] = nullptr;
    sensors["tofError"] = tofTimeout ? "TIMEOUT" : "INVALID_RANGE";
  }

  sensors["tofValid"] = tofValid;
  sensors["tofTimeout"] = tofTimeout;

  JsonObject transport = doc.createNestedObject("transport");
  transport["wifiRssiDbm"] = WiFi.RSSI();
  transport["pingOk"] = pingOk;

  char payload[512];
  size_t payloadLen = serializeJson(doc, payload, sizeof(payload));

  if (payloadLen == 0 || payloadLen >= sizeof(payload)) {
    Serial.println("JSON serialize failed or payload too large");
    return;
  }

  bool ok = mqttClient.publish(TOPIC_SENSOR_RAW, payload, false);

  Serial.print(ok ? "MQTT PUB OK: " : "MQTT PUB FAIL: ");
  Serial.println(payload);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("ESP32 sensor raw MQTT boot");

  Wire.begin(21, 22);
  Wire.setClock(100000);

  pinMode(PIR_PIN, INPUT_PULLDOWN);

  setupWiFi();
  setupMqtt();
  setupToF();

  Serial.println("SYSTEM READY");
}

void loop() {
  ensureWiFiConnected();
  ensureMqttConnected();
  mqttClient.loop();

  uint32_t now = millis();
  if (now - lastSampleAt >= SAMPLE_INTERVAL_MS) {
    lastSampleAt = now;

    if (WiFi.status() == WL_CONNECTED && mqttClient.connected()) {
      publishSensorRaw();
    }
  }
}

#include <esp_now.h>
#include <WiFi.h>
#include <DHT.h>

#define DHTPIN 4
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

// Sensor and Motor Pin Configuration (Adjust to your physical board pinout)
const int trigLeft = 12, echoLeft = 13;
const int trigRight = 14, echoRight = 27;
const int irLeft = 25, irRight = 26;
const int mqGasPin = 34; // ESP32 Analog Read Pin (ADC1)

// Motor Driver Outputs
const int motorLeftFwd = 16, motorLeftRev = 17;
const int motorRightFwd = 18, motorRightRev = 19;

// ESP-NOW Mesh Data Communication Structure
typedef struct struct_message {
    char status_flag[12];
    float temp;
    float humid;
    int gas;
    bool human_alert;
} struct_message;

struct_message meshData;
uint8_t nextRelayAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF}; // Broadcast network address

bool globalAlarmState = false;

void moveForward() {
  digitalWrite(motorLeftFwd, HIGH); digitalWrite(motorLeftRev, LOW);
  digitalWrite(motorRightFwd, HIGH); digitalWrite(motorRightRev, LOW);
}

void stopRover() {
  digitalWrite(motorLeftFwd, LOW); digitalWrite(motorLeftRev, LOW);
  digitalWrite(motorRightFwd, LOW); digitalWrite(motorRightRev, LOW);
}

long getDistance(int trig, int echo) {
  digitalWrite(trig, LOW); delayMicroseconds(2);
  digitalWrite(trig, HIGH); delayMicroseconds(10);
  digitalWrite(trig, LOW);
  return pulseIn(echo, HIGH) * 0.034 / 2;
}

void setup() {
  Serial.begin(115200); // Communication port to Pi 4 Brain
  dht.begin();

  pinMode(trigLeft, OUTPUT); pinMode(echoLeft, INPUT);
  pinMode(trigRight, OUTPUT); pinMode(echoRight, INPUT);
  pinMode(irLeft, INPUT); pinMode(irRight, INPUT);
  pinMode(motorLeftFwd, OUTPUT); pinMode(motorLeftRev, OUTPUT);
  pinMode(motorRightFwd, OUTPUT); pinMode(motorRightRev, OUTPUT);

  // Initialize Wireless ESP-NOW Mesh Layer
  WiFi.mode(WIFI_STA);
  if (esp_now_init() != ESP_OK) return;

  esp_now_peer_info_t peerInfo;
  memcpy(peerInfo.peer_addr, nextRelayAddress, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  esp_now_add_peer(&peerInfo);
}

void loop() {
  // 1. Gather Telemetry Performance Matrix
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  int gas = analogRead(mqGasPin);
  long distL = getDistance(trigLeft, echoLeft);
  long distR = getDistance(trigRight, echoRight);
  int irLVal = digitalRead(irLeft);
  int irRVal = digitalRead(irRight);

  // Send structured CSV telemetry upward to the Pi Brain via physical serial link
  Serial.printf("%.1f,%.1f,%d,%ld,%ld\n", t, h, gas, distL, distR);

  // 2. Parse Incoming Vision AI Decision Targets from the Pi
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "H") {
      globalAlarmState = true;
      stopRover(); // Lock movement instantly if a miner is detected
    } else if (command == "N") {
      globalAlarmState = false;
    }
  }

  // 3. Fallback Autonomous Navigation Controls & Obstacle Logic
  if (globalAlarmState) {
    stopRover();
  } else {
    // Standard safety stop logic if local sensors detect barriers or drops
    if (distL < 20 || distR < 20 || irLVal == HIGH || irRVal == HIGH) {
      stopRover();
    } else {
      moveForward();
    }
  }

  // 4. Wrap and Fire Telemetry via ESP-NOW Mesh Protocol down the link chain
  meshData.temp = t;
  meshData.humid = h;
  meshData.gas = gas;
  meshData.human_alert = globalAlarmState;
  strcpy(meshData.status_flag, globalAlarmState ? "EMERGENCY" : "NOMINAL");

  esp_now_send(nextRelayAddress, (uint8_t *) &meshData, sizeof(meshData));

  delay(100);
}
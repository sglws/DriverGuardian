// DriverGuardian - Arduino Uno: gas sensors and seat vibration.
// USB to the Raspberry Pi, 115200 baud (the same cable powers the Uno).
//
//   MQ-3 (alcohol) AO -> A0    MQ-2 (smoke) AO -> A1    BTS7960 RPWM -> pin 6
//
// To the Pi, 5 times per second:  SEN,mq3=<0-1023>,mq2=<0-1023>,warm=<0|1>,up=<s>
// From the Pi:  "ID?" -> "DGUNO,1"    "1" -> seat motor on for 3 s
// Keep WARMUP_MS equal to ARDUINO_WARMUP_SEC in app/config.py.

#include <Arduino.h>

const int RPWM_PIN = 6;
const int MQ3_PIN  = A0;
const int MQ2_PIN  = A1;

const unsigned long BURST_MS = 3000;
const unsigned long REPORT_INTERVAL_MS = 200;
const unsigned long WARMUP_MS = 30000UL;
const float SMOOTHING = 0.2;        // moving-average weight of each new reading

unsigned long motorStartTime = 0;
bool motorRunning = false;
float mq3Avg = -1;
float mq2Avg = -1;
unsigned long lastReport = 0;
String rx = "";

void handleCommand(String cmd) {
  cmd.trim();
  if (cmd == "ID?") {
    Serial.println("DGUNO,1");
  } else if ((cmd == "1" || cmd == "S" || cmd == "s") && !motorRunning) {
    digitalWrite(RPWM_PIN, HIGH);
    motorStartTime = millis();
    motorRunning = true;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(RPWM_PIN, OUTPUT);
  digitalWrite(RPWM_PIN, LOW);      // motor off at boot
  pinMode(MQ3_PIN, INPUT);
  pinMode(MQ2_PIN, INPUT);
  Serial.println("DGUNO,1");        // lets the Pi recognise this port
}

void loop() {
  while (Serial.available()) {      // never blocks
    char c = Serial.read();
    if (c == '\n') {
      handleCommand(rx);
      rx = "";
    } else if (c != '\r' && rx.length() < 32) {
      rx += c;
    }
  }

  unsigned long now = millis();
  if (motorRunning && now - motorStartTime >= BURST_MS) {
    digitalWrite(RPWM_PIN, LOW);
    motorRunning = false;
  }

  if (now - lastReport < REPORT_INTERVAL_MS) return;
  lastReport = now;

  int mq3 = analogRead(MQ3_PIN);
  int mq2 = analogRead(MQ2_PIN);
  mq3Avg = mq3Avg < 0 ? mq3 : mq3Avg + SMOOTHING * (mq3 - mq3Avg);
  mq2Avg = mq2Avg < 0 ? mq2 : mq2Avg + SMOOTHING * (mq2 - mq2Avg);

  Serial.print("SEN,mq3=");  Serial.print((int)(mq3Avg + 0.5));
  Serial.print(",mq2=");     Serial.print((int)(mq2Avg + 0.5));
  Serial.print(",warm=");    Serial.print(now >= WARMUP_MS ? 1 : 0);
  Serial.print(",up=");      Serial.println(now / 1000UL);
}

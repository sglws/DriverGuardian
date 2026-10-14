// ============================================================
// DriverGuardian - Arduino Uno: cabin air sensors + fan
// ============================================================
// Connected to the Raspberry Pi by USB (the same cable powers the Uno).
//
//   MQ-3  alcohol            AO -> A0      (VCC -> 5V, GND -> GND)
//   MQ-2  smoke / LPG / gas  AO -> A1      (VCC -> 5V, GND -> GND)
//   BTS7960 fan driver       RPWM -> pin 6 (motor power from its own supply)
//
// To the Pi (115200 baud, every REPORT_INTERVAL_MS):
//   SEN,mq3=<0-1023>,mq2=<0-1023>,warm=<0|1>,up=<seconds since power-on>
// The sensor values are shown on the dashboard and recorded; they do not
// change the risk level.
//
// From the Pi:
//   ID?        -> answers "DGUNO,1" (how the Pi finds this board's port)
//   1 / S / s  -> pin 6 HIGH for BURST_DURATION (the fan). The Pi sends "1"
//                 when the driver falls asleep or has a microsleep, and again
//                 every 10 s while it lasts (ARDUINO_FAN_CASES in config.py).
//
// Keep WARMUP_MS equal to ARDUINO_WARMUP_SEC in app/config.py.

#include <Arduino.h>

// ==========================================
// PIN DEFINITIONS
// ==========================================
const int RPWM_PIN = 6;      // Connected to BTS7960 RPWM (Fan / Safety Actuator)
const int MQ3_PIN  = A0;     // MQ-3 Alcohol Sensor Analog In
const int MQ2_PIN  = A1;     // MQ-2 Smoke/Gas Sensor Analog In

// ==========================================
// TIMING & REPORTING CONFIGURATION
// ==========================================
const unsigned long BURST_DURATION = 3000;       // 3 seconds fan safety burst
const unsigned long REPORT_INTERVAL_MS = 200;    // 5 reports per second to Pi
const unsigned long WARMUP_MS = 30000UL;         // 30 s MQ heater warm-up
const float SMOOTHING = 0.2;                     // Exponential moving average weight

// ==========================================
// STATE VARIABLES
// ==========================================
unsigned long motorStartTime = 0;
bool motorRunning = false;

float mq3Avg = -1;
float mq2Avg = -1;
unsigned long lastReport = 0;
String rx = "";

// ==========================================
// COMMAND HANDLER
// ==========================================
void handleCommand(String cmd) {
  cmd.trim();
  if (cmd == "ID?") {
    Serial.println("DGUNO,1");
  }
  else if ((cmd == "1" || cmd == "S" || cmd == "s") && !motorRunning) {
    digitalWrite(RPWM_PIN, HIGH); // Full speed ON
    motorStartTime = millis();
    motorRunning = true;
    Serial.println("HIGH RISK DETECTED: Fan activated for 3 seconds!");
  }
}

// ==========================================
// SETUP
// ==========================================
void setup() {
  // Unified baud rate for Pi communication and sensor streaming
  Serial.begin(115200);

  // Configure pins
  pinMode(RPWM_PIN, OUTPUT);
  digitalWrite(RPWM_PIN, LOW); // Fail-safe: OFF at boot

  pinMode(MQ3_PIN, INPUT);
  pinMode(MQ2_PIN, INPUT);

  // Hello signal after reset for Pi port identification
  Serial.println("DGUNO,1");
}

// ==========================================
// MAIN LOOP
// ==========================================
void loop() {
  // ------------------------------------------
  // 1. NON-BLOCKING SERIAL COMMAND PROCESSING
  // ------------------------------------------
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      handleCommand(rx);
      rx = "";
    } else if (c != '\r' && rx.length() < 32) {
      rx += c;
    }
  }

  unsigned long now = millis();

  // ------------------------------------------
  // 2. HANDLE THE 3-SECOND FAN SAFETY TIMER
  // ------------------------------------------
  if (motorRunning && (now - motorStartTime >= BURST_DURATION)) {
    digitalWrite(RPWM_PIN, LOW); // Turn fan OFF
    motorRunning = false;
    Serial.println("Burst complete. Fan turned OFF.");
  }

  // ------------------------------------------
  // 3. SENSOR REPORTING INTERVAL (Every 200ms)
  // ------------------------------------------
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

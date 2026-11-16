#include <Arduino.h>
#include "BluetoothSerial.h"

// ============================================================
// BLUETOOTH
// ============================================================
#if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
#error Bluetooth is not enabled or not available. Select a classic ESP32 board.
#endif

BluetoothSerial SerialBT;

// ============================================================
// MOTOR PINS
// ============================================================
const int IN1 = 26;        // Left Motor Direction 1
const int IN2 = 27;        // Left Motor Direction 2
const int IN3 = 14;        // Right Motor Direction 1
const int IN4 = 12;        // Right Motor Direction 2

const int ENA_PIN = 32;    // Left Motor PWM
const int ENB_PIN = 33;    // Right Motor PWM

// ============================================================
// LED PINS
// ============================================================
const int LED_LEFT_PIN  = 4;
const int LED_RIGHT_PIN = 5;

unsigned long lastLedToggle = 0;
bool ledState = false;

// ============================================================
// SENSOR PINS
// ============================================================
const int IR_FRONT_PIN = 34;
const int IR_REAR_PIN  = 35;

const int US_FRONT_TRIG = 15;
const int US_FRONT_ECHO = 18;

const int US_REAR_TRIG  = 23;
const int US_REAR_ECHO  = 19;

// ============================================================
// OBSTACLE DETECTION
// ============================================================
const float OBSTACLE_THRESHOLD_CM = 10.0;
const int OBSTACLE_FILTER_THRESHOLD = 3;

int frontObstacleCounter = 0;
int rearObstacleCounter  = 0;

// ============================================================
// PWM
// ============================================================
const int PWM_FREQ = 20;
const int PWM_RES  = 8;

// ============================================================
// NORMAL DRIVING
// ============================================================
const int MIN_MOTOR_SPEED = 100;
const int MAX_MOTOR_SPEED = 255;
const int SPEED_RAMP_STEP = 5;

int initialSpeed = 0;

int currentLeftSpeed  = 0;
int currentRightSpeed = 0;

// ============================================================
// BLUETOOTH FAIL-SAFE & STARTUP HANDSHAKE
// ============================================================
const unsigned long BT_TIMEOUT_MS = 6000;

unsigned long lastMessageAt = 0;
bool linkFailed = true;
bool initialConnectionReceived = false; // motors stay locked until the Pi speaks

String lastCase = "NONE";

// ============================================================
// CURRENT RISK
// ============================================================
String currentRisk = "SAFE";

// ============================================================
// HIGH-RISK PARKING MANEUVER
// ============================================================
enum ParkPhase {
  PARK_IDLE,
  PARK_ARC,
  PARK_REALIGN,
  PARK_STRAIGHT,
  PARK_STOPPED
};

ParkPhase parkPhase = PARK_IDLE;
unsigned long parkPhaseStart = 0;

// ------------------------------------------------------------
// PARKING SPEEDS & TIMING
// ------------------------------------------------------------
const int ARC_FAST = 190;
const int ARC_SLOW = 60;
const int STRAIGHT_L = 60;
const int STRAIGHT_R = 200;

const unsigned long ARC_MS = 15000;
const unsigned long STRAIGHT_MS = 3000;

const unsigned long T_REV_RIGHT_MS = 4000;
const unsigned long T_REV_LEFT_MS  = 4000;

unsigned long realignMs = 0;
bool realignTurnLeft = true;

const unsigned long MAX_PULLOVER_TIMEOUT_MS = 30000;
unsigned long highRiskStartTime = 0;

// ============================================================
// GENERAL TIMING
// ============================================================
unsigned long lastLoopExecution = 0;
const unsigned long LOOP_INTERVAL_MS = 100;

// ============================================================
// TELEMETRY TO THE PI (dashboard only - nothing here steers the car)
//   TEL,risk,leftPWM,rightPWM,basePWM,frontCm,rearCm,irFront,irRear,estop,linkFailed,pulloverMs
// estop: 0 none, 1 obstacle, 2 edge. Distances 999 = nothing in range.
// Must match _parse_telemetry() in app/outputs/esp32_link.py (12 fields).
// ============================================================
const unsigned long TELEMETRY_INTERVAL_MS = 250;
unsigned long lastTelemetryAt = 0;
float telFrontCm = 999.0;
float telRearCm  = 999.0;
int telIrFront = 0;
int telIrRear  = 0;
int telEstop   = 0;

void sendTelemetry() {
  unsigned long now = millis();
  if (now - lastTelemetryAt < TELEMETRY_INTERVAL_MS) return;
  lastTelemetryAt = now;
  if (!SerialBT.hasClient()) return;   // never block the control loop on a missing Pi
  unsigned long pulloverMs = (currentRisk == "HIGH" && highRiskStartTime != 0) ? now - highRiskStartTime : 0;
  SerialBT.printf("TEL,%s,%d,%d,%d,%.1f,%.1f,%d,%d,%d,%d,%lu\n",
                  currentRisk.c_str(), currentLeftSpeed, currentRightSpeed, initialSpeed,
                  telFrontCm, telRearCm, telIrFront, telIrRear, telEstop,
                  linkFailed ? 1 : 0, pulloverMs);
}

// ============================================================
// MOTOR FUNCTIONS
// ============================================================
void stopMotors() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);
  ledcWrite(ENA_PIN, 0);
  ledcWrite(ENB_PIN, 0);
  currentLeftSpeed = 0;
  currentRightSpeed = 0;
}

void driveMotors(int leftSpeed, int rightSpeed) {
  currentLeftSpeed = leftSpeed;
  currentRightSpeed = rightSpeed;

  // LEFT MOTOR
  if (leftSpeed > 0) {
    digitalWrite(IN1, HIGH);
    digitalWrite(IN2, LOW);
    ledcWrite(ENA_PIN, leftSpeed);
  } else {
    digitalWrite(IN1, LOW);
    digitalWrite(IN2, LOW);
    ledcWrite(ENA_PIN, 0);
  }

  // RIGHT MOTOR
  if (rightSpeed > 0) {
    digitalWrite(IN3, HIGH);
    digitalWrite(IN4, LOW);
    ledcWrite(ENB_PIN, rightSpeed);
  } else {
    digitalWrite(IN3, LOW);
    digitalWrite(IN4, LOW);
    ledcWrite(ENB_PIN, 0);
  }
}

void brakeMotors() {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, HIGH);
  ledcWrite(ENA_PIN, 255);
  ledcWrite(ENB_PIN, 255);
  currentLeftSpeed = 0;
  currentRightSpeed = 0;
}

void releaseMotors() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);
  ledcWrite(ENA_PIN, 0);
  ledcWrite(ENB_PIN, 0);
}

const char* parkPhaseName(ParkPhase p) {
  switch (p) {
    case PARK_ARC:      return "PARK PHASE 1 - RIGHT ARC";
    case PARK_REALIGN:  return realignTurnLeft ? "PARK PHASE 2 - COUNTER-STEER LEFT" : "PARK PHASE 2 - FINISH RIGHT TURN";
    case PARK_STRAIGHT: return "PARK PHASE 3 - STRAIGHT";
    case PARK_STOPPED:  return "PARKING COMPLETE";
    default:            return "PARK IDLE";
  }
}

void enterParkPhase(ParkPhase p) {
  parkPhase = p;
  parkPhaseStart = millis();
  Serial.printf(">>> %s at %lu ms\n", parkPhaseName(p), parkPhaseStart);
}

void startRightParking() {
  Serial.println();
  Serial.println("==========================================");
  Serial.println("HIGH RISK DETECTED");
  Serial.println("STARTING RIGHT-SIDE PULL-OVER");
  Serial.println("==========================================");

  unsigned long residual = ARC_MS % T_REV_RIGHT_MS;
  float residualDeg = 360.0f * residual / T_REV_RIGHT_MS;

  if (residualDeg <= 180.0f) {
    realignTurnLeft = true;
    realignMs = (unsigned long)(T_REV_LEFT_MS * (residualDeg / 360.0f));
  } else {
    realignTurnLeft = false;
    realignMs = T_REV_RIGHT_MS - residual;
  }

  Serial.printf("Arc: %lu ms | L=%d R=%d\n", ARC_MS, ARC_FAST, ARC_SLOW);
  Serial.printf("Heading after arc: %.1f degrees right\n", residualDeg);
  Serial.printf("Realign: %s for %lu ms\n", realignTurnLeft ? "LEFT" : "RIGHT", realignMs);
  Serial.printf("Straight: %lu ms | L=%d R=%d\n", STRAIGHT_MS, STRAIGHT_L, STRAIGHT_R);
  Serial.println("==========================================");

  highRiskStartTime = millis();
  enterParkPhase(PARK_ARC);
}

void executeRightParking() {
  unsigned long now = millis();
  unsigned long elapsed = now - parkPhaseStart;

  // Already stopped: release the brake once, never re-trigger the timeout.
  if (parkPhase == PARK_STOPPED) {
    if (elapsed >= 300) releaseMotors();
    return;
  }

  if (highRiskStartTime != 0 && now - highRiskStartTime >= MAX_PULLOVER_TIMEOUT_MS) {
    Serial.println("PARKING TIMEOUT -> BRAKING");
    brakeMotors();
    enterParkPhase(PARK_STOPPED);
    return;
  }

  if (parkPhase == PARK_ARC) {
    driveMotors(ARC_FAST, ARC_SLOW);
    if (elapsed >= ARC_MS) enterParkPhase(PARK_REALIGN);
  }
  else if (parkPhase == PARK_REALIGN) {
    if (realignTurnLeft) {
      driveMotors(ARC_SLOW, ARC_FAST);
    } else {
      driveMotors(ARC_FAST, ARC_SLOW);
    }
    if (elapsed >= realignMs) enterParkPhase(PARK_STRAIGHT);
  }
  else if (parkPhase == PARK_STRAIGHT) {
    driveMotors(STRAIGHT_L, STRAIGHT_R);
    if (elapsed >= STRAIGHT_MS) {
      Serial.println("RIGHT PARKING MANEUVER COMPLETE");
      brakeMotors();
      enterParkPhase(PARK_STOPPED);
    }
  }
}

void updateHazardLEDs(bool emergencyStop) {
  unsigned long currentMillis = millis();

  if (emergencyStop) {
    int blinkInterval = 150;
    if (currentMillis - lastLedToggle >= blinkInterval) {
      lastLedToggle = currentMillis;
      ledState = !ledState;
      digitalWrite(LED_LEFT_PIN, ledState ? HIGH : LOW);
      digitalWrite(LED_RIGHT_PIN, ledState ? HIGH : LOW);
    }
    return;
  }

  if (currentRisk == "MEDIUM") {
    int blinkInterval = 500;
    if (currentMillis - lastLedToggle >= blinkInterval) {
      lastLedToggle = currentMillis;
      ledState = !ledState;
      digitalWrite(LED_LEFT_PIN, ledState ? HIGH : LOW);
      digitalWrite(LED_RIGHT_PIN, ledState ? HIGH : LOW);
    }
    return;
  }

  if (currentRisk == "HIGH") {
    int blinkInterval = 150;
    if (currentMillis - lastLedToggle >= blinkInterval) {
      lastLedToggle = currentMillis;
      ledState = !ledState;

      if (parkPhase == PARK_ARC || (parkPhase == PARK_REALIGN && !realignTurnLeft)) {
        digitalWrite(LED_LEFT_PIN, LOW);
        digitalWrite(LED_RIGHT_PIN, ledState ? HIGH : LOW);
      }
      else if (parkPhase == PARK_REALIGN && realignTurnLeft) {
        digitalWrite(LED_RIGHT_PIN, LOW);
        digitalWrite(LED_LEFT_PIN, ledState ? HIGH : LOW);
      }
      else {
        digitalWrite(LED_LEFT_PIN, ledState ? HIGH : LOW);
        digitalWrite(LED_RIGHT_PIN, ledState ? HIGH : LOW);
      }
    }
    return;
  }

  digitalWrite(LED_LEFT_PIN, LOW);
  digitalWrite(LED_RIGHT_PIN, LOW);
  ledState = false;
}

float readUltrasonic(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH, 6000);
  if (duration == 0) return 999.0;
  return (duration * 0.0343) / 2.0;
}

void setup() {
  Serial.begin(115200);
  delay(500);

  randomSeed(analogRead(36));
  initialSpeed = random(180, MAX_MOTOR_SPEED + 1);

  Serial.println("======================================");
  Serial.println("DriverGuardian");
  Serial.printf("Normal Base Speed: %d PWM\n", initialSpeed);
  Serial.println("======================================");

  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  pinMode(LED_LEFT_PIN, OUTPUT);
  pinMode(LED_RIGHT_PIN, OUTPUT);
  digitalWrite(LED_LEFT_PIN, LOW);
  digitalWrite(LED_RIGHT_PIN, LOW);

  ledcAttach(ENA_PIN, PWM_FREQ, PWM_RES);
  ledcAttach(ENB_PIN, PWM_FREQ, PWM_RES);

  pinMode(IR_FRONT_PIN, INPUT);
  pinMode(IR_REAR_PIN, INPUT);
  pinMode(US_FRONT_TRIG, OUTPUT);
  pinMode(US_FRONT_ECHO, INPUT);
  pinMode(US_REAR_TRIG, OUTPUT);
  pinMode(US_REAR_ECHO, INPUT);

  stopMotors();

  SerialBT.begin("DriverGuardian_ESP32");
  Serial.println("Bluetooth SPP started: DriverGuardian_ESP32");
  Serial.println("Waiting for Raspberry Pi signal...");

  lastMessageAt = millis();
  linkFailed = true;
  initialConnectionReceived = false; // Ensure it waits on boot
}

void loop() {
  // ==========================================================
  // 1. BLUETOOTH PROCESSING
  // ==========================================================
  static String buf;

  while (SerialBT.available()) {
    char c = SerialBT.read();

    if (c == '\n') {
      buf.trim();
      int comma = buf.indexOf(',');

      if (comma > 0) {
        String risk = buf.substring(0, comma);
        String reasonCase = buf.substring(comma + 1);

        risk.trim();
        reasonCase.trim();

        if (risk == "SAFE" || risk == "LOW" || risk == "MEDIUM" || risk == "HIGH") {
          if (risk != currentRisk || reasonCase != lastCase) {
            Serial.printf("BT Received -> State: %s (case=%s)\n", risk.c_str(), reasonCase.c_str());
          }

          // first valid command: unlock the motors
          initialConnectionReceived = true;

          if (risk == "HIGH" && currentRisk != "HIGH") {
            currentRisk = "HIGH";
            startRightParking();
          } else {
            currentRisk = risk;
          }

          lastCase = reasonCase;
          lastMessageAt = millis();
          linkFailed = false;
        }
      }
      buf = "";
    }
    else if (c != '\r') {
      buf += c;
      if (buf.length() > 64) {
        buf = "";
      }
    }
  }

  // ==========================================================
  // 2. USB SERIAL MANUAL OVERRIDE
  // ==========================================================
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    input.toUpperCase();

    if (input == "SAFE" || input == "LOW" || input == "MEDIUM") {
      initialConnectionReceived = true; // Unlock via manual override too
      currentRisk = input;
      lastMessageAt = millis();
      Serial.print(">> MANUAL SERIAL STATE OVERRIDE: ");
      Serial.println(currentRisk);
    }
    else if (input == "HIGH") {
      initialConnectionReceived = true;
      if (currentRisk != "HIGH") {
        currentRisk = "HIGH";
        lastMessageAt = millis();
        startRightParking();
      }
    }
    else if (input.toInt() >= MIN_MOTOR_SPEED && input.toInt() <= MAX_MOTOR_SPEED) {
      initialSpeed = input.toInt();
      Serial.printf(">> BASE SPEED UPDATED TO: %d PWM\n", initialSpeed);
    }
  }

  // ==========================================================
  // 3. 10 Hz PHYSICAL CONTROL LOOP
  // ==========================================================
  unsigned long currentMillis = millis();

  if (currentMillis - lastLoopExecution < LOOP_INTERVAL_MS) {
    return;
  }
  lastLoopExecution = currentMillis;

  // Before any early return below, so the dashboard keeps updating during
  // the startup wait, an emergency stop and the pull-over (last tick's values).
  sendTelemetry();

  // ==========================================================
  // 4. STARTUP BLOCK: STAY STOPPED UNTIL PI SIGNAL RECEIVED
  // ==========================================================
  if (!initialConnectionReceived) {
    stopMotors();
    updateHazardLEDs(false);

    static unsigned long lastWaitLog = 0;
    if (currentMillis - lastWaitLog > 3000) {
      lastWaitLog = currentMillis;
      Serial.println("SYSTEM WAITING: No signal from Raspberry Pi yet. Motors locked.");
    }
    return; // Skip the rest of the loop until the Pi sends a message
  }

  // ==========================================================
  // 5. READ SENSORS
  // ==========================================================
  int irFrontState = digitalRead(IR_FRONT_PIN);
  int irRearState  = digitalRead(IR_REAR_PIN);
  float usFrontDist = readUltrasonic(US_FRONT_TRIG, US_FRONT_ECHO);
  float usRearDist  = readUltrasonic(US_REAR_TRIG, US_REAR_ECHO);
  telFrontCm = usFrontDist;
  telRearCm  = usRearDist;
  telIrFront = irFrontState == HIGH ? 1 : 0;
  telIrRear  = irRearState == HIGH ? 1 : 0;

  // ==========================================================
  // 6. ULTRASONIC FILTER
  // ==========================================================
  if (usFrontDist > 0.0 && usFrontDist <= OBSTACLE_THRESHOLD_CM) {
    frontObstacleCounter++;
  } else {
    frontObstacleCounter = 0;
  }

  if (usRearDist > 0.0 && usRearDist <= OBSTACLE_THRESHOLD_CM) {
    rearObstacleCounter++;
  } else {
    rearObstacleCounter = 0;
  }

  // ==========================================================
  // 7. BLUETOOTH FAIL-SAFE (Only active after initial connection)
  // ==========================================================
  if (currentMillis - lastMessageAt > BT_TIMEOUT_MS) {
    if (!linkFailed) {
      Serial.println("BLUETOOTH FAIL-SAFE: Raspberry Pi connection lost");
      Serial.println("FORCING HIGH-RISK RIGHT PULL-OVER");
      linkFailed = true;
    }

    if (currentRisk != "HIGH") {
      currentRisk = "HIGH";
      startRightParking();
    }
  }

  // ==========================================================
  // 8. PHYSICAL EMERGENCY OVERRIDE
  // ==========================================================
  bool isCliffDetected = (irFrontState == HIGH || irRearState == HIGH);
  bool isObstacleDetected = (frontObstacleCounter >= OBSTACLE_FILTER_THRESHOLD) ||
                            (rearObstacleCounter >= OBSTACLE_FILTER_THRESHOLD);
  bool emergencyStop = isCliffDetected || isObstacleDetected;
  telEstop = isCliffDetected ? 2 : isObstacleDetected ? 1 : 0;

  if (emergencyStop) {
    stopMotors();
    updateHazardLEDs(true);

    static unsigned long lastLogTime = 0;
    if (currentMillis - lastLogTime > 1000) {
      lastLogTime = currentMillis;
      if (isCliffDetected) {
        Serial.println("GLOBAL OVERRIDE: CLIFF DETECTED -> EMERGENCY STOP");
      } else {
        Serial.printf("GLOBAL OVERRIDE: OBSTACLE <=10cm -> EMERGENCY STOP (Front: %.1f cm | Rear: %.1f cm)\n", usFrontDist, usRearDist);
      }
    }
    return;
  }

  // ==========================================================
  // 9. HIGH-RISK PARKING
  // ==========================================================
  if (currentRisk == "HIGH") {
    executeRightParking();
    updateHazardLEDs(false);
    return;
  }

  // ==========================================================
  // 10. NORMAL SAFE / LOW / MEDIUM DRIVING
  // ==========================================================
  int stateTargetLeft = initialSpeed;
  int stateTargetRight = initialSpeed;

  if (currentRisk == "SAFE") {
    stateTargetLeft = initialSpeed;
    stateTargetRight = initialSpeed;
  }
  else if (currentRisk == "LOW") {
    stateTargetLeft = max((int)(initialSpeed * 0.70), MIN_MOTOR_SPEED);
    stateTargetRight = stateTargetLeft;
  }
  else if (currentRisk == "MEDIUM") {
    stateTargetLeft = max((int)(initialSpeed * 0.50), MIN_MOTOR_SPEED);
    stateTargetRight = stateTargetLeft;
  }

  int activeTargetLeft = stateTargetLeft;
  int activeTargetRight = stateTargetRight;

  if (currentLeftSpeed != currentRightSpeed) {
    activeTargetLeft = MIN_MOTOR_SPEED;
    activeTargetRight = MIN_MOTOR_SPEED;

    if (currentLeftSpeed == 0) currentLeftSpeed = MIN_MOTOR_SPEED;
    if (currentRightSpeed == 0) currentRightSpeed = MIN_MOTOR_SPEED;

    if (currentLeftSpeed > MIN_MOTOR_SPEED) {
      currentLeftSpeed = max(currentLeftSpeed - SPEED_RAMP_STEP, MIN_MOTOR_SPEED);
    } else if (currentLeftSpeed < MIN_MOTOR_SPEED) {
      currentLeftSpeed = min(currentLeftSpeed + SPEED_RAMP_STEP, MIN_MOTOR_SPEED);
    }

    if (currentRightSpeed > MIN_MOTOR_SPEED) {
      currentRightSpeed = max(currentRightSpeed - SPEED_RAMP_STEP, MIN_MOTOR_SPEED);
    } else if (currentRightSpeed < MIN_MOTOR_SPEED) {
      currentRightSpeed = min(currentRightSpeed + SPEED_RAMP_STEP, MIN_MOTOR_SPEED);
    }
  }
  else {
    if (currentLeftSpeed == 0 && activeTargetLeft > 0) {
      currentLeftSpeed = MIN_MOTOR_SPEED;
      currentRightSpeed = MIN_MOTOR_SPEED;
    }

    if (currentLeftSpeed < activeTargetLeft) {
      currentLeftSpeed = min(currentLeftSpeed + SPEED_RAMP_STEP, activeTargetLeft);
      currentRightSpeed = currentLeftSpeed;
    }
    else if (currentLeftSpeed > activeTargetLeft) {
      currentLeftSpeed = max(currentLeftSpeed - SPEED_RAMP_STEP, activeTargetLeft);
      currentRightSpeed = currentLeftSpeed;
    }
  }

  updateHazardLEDs(false);
  driveMotors(currentLeftSpeed, currentRightSpeed);

  static String lastPrintedRisk = "";
  if (currentRisk != lastPrintedRisk) {
    Serial.printf("%s State | Left: %d PWM | Right: %d PWM\n",
                  currentRisk.c_str(),
                  currentLeftSpeed,
                  currentRightSpeed);
    lastPrintedRisk = currentRisk;
  }
}

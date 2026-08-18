/*
 * DriverGuardian_ESP32.ino
 * -------------------------
 * Receives "RISK,CASE\n" lines from the Raspberry Pi over classic
 * Bluetooth (SPP) and drives a buzzer, seat-vibration motor, status LEDs,
 * and a hazard-lights relay accordingly.
 *
 * BOARD: a classic ESP32 (e.g. "ESP32 Dev Module" / WROOM-32). ESP32-S3,
 * -C3, and -S2 do NOT have classic Bluetooth (BLE only) and cannot run
 * this sketch as-is - see the README for the BLE alternative if that's
 * what you have.
 *
 * PROTOCOL
 *   Each line from the Pi: "<RISK>,<CASE>\n"
 *     RISK in {SAFE, LOW, MEDIUM, HIGH}
 *     CASE examples: NONE, SLEEP, LEAN, LEAN_PROLONGED, TURN,
 *                     TURN_PROLONGED, SEATBELT, PHONE, PHONE_REPEAT,
 *                     CONSUMPTION, CONSUMPTION_REPEAT, YAWN, ABSENT, BLOCKED
 *   Physical actuators are driven by RISK (matches the project's action
 *   table exactly: SAFE=continue, LOW=audio only, MEDIUM=vibration+amber,
 *   HIGH=buzzer+vibration+hazard+"taking control"). CASE is printed to the
 *   USB serial console for diagnostics/logging - extend applyState() if
 *   you add a display and want to show it there too.
 *
 * HEARTBEAT / CASE 8 (Bluetooth Failure -> HIGH -> Safe stop mode)
 *   The Pi sends its state on a fixed interval regardless of change (see
 *   ESP32_SEND_INTERVAL_SEC in app/config.py), so silence itself is a
 *   signal. If no line arrives for BT_TIMEOUT_MS, this firmware assumes
 *   the link (or the Pi) has failed and fails safe on its own - it can't
 *   wait on a Pi that may be the thing that's broken.
 */

#include "BluetoothSerial.h"

#if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
#error Bluetooth is not enabled or not available. In Arduino IDE, Tools > Board, pick a plain "ESP32 Dev Module" (classic BT) - not an S3/C3/S2 board, and make sure Tools > Partition Scheme includes Bluetooth.
#endif

BluetoothSerial SerialBT;

// ---- Pin map (avoids ESP32 boot-strapping pins: 0, 2 handled carefully, 5, 12, 15) ----
const int BUZZER_PIN       = 25;  // piezo buzzer / active buzzer module
const int VIBRATION_PIN    = 26;  // seat vibration motor, via transistor/MOSFET
const int GREEN_LED_PIN    = 27;  // SAFE indicator
const int AMBER_LED_PIN    = 14;  // LOW/MEDIUM warning indicator
const int RED_LED_PIN      = 13;  // HIGH danger indicator
const int HAZARD_RELAY_PIN = 33;  // relay module driving actual hazard lights
const int BT_STATUS_LED    = 2;   // onboard LED on most ESP32 DevKits - Bluetooth client connected

const unsigned long BT_TIMEOUT_MS  = 3000;  // no message this long -> link failure (Case 8)
const unsigned long BLINK_FAST_MS  = 150;   // HIGH-risk blink rate
const unsigned long BLINK_SLOW_MS  = 600;   // LOW-risk blink rate
const unsigned long MEDIUM_BEEP_MS = 400;   // MEDIUM intermittent-beep half-period

String lastRisk = "SAFE";
String lastCase = "NONE";
unsigned long lastMessageAt = 0;
bool linkFailed = false;

// State used by applyState()'s non-blocking blink/beep patterns.
unsigned long lastBlinkToggle = 0;
bool blinkState = false;
unsigned long lastBeepToggle = 0;
bool beepState = false;

void setAllOff() {
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(AMBER_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(HAZARD_RELAY_PIN, LOW);
  noTone(BUZZER_PIN);
  digitalWrite(VIBRATION_PIN, LOW);
}

void applyState(const String &risk, const String &reasonCase) {
  unsigned long now = millis();

  // Every branch below fully owns the buzzer each call (tone() or
  // noTone(), never left implicit) - a state that doesn't explicitly
  // silence it would leave it stuck on from whatever the previous,
  // louder tier last set, e.g. de-escalating MEDIUM -> SAFE.
  if (risk == "SAFE") {
    digitalWrite(GREEN_LED_PIN, HIGH);
    digitalWrite(AMBER_LED_PIN, LOW);
    digitalWrite(RED_LED_PIN, LOW);
    digitalWrite(HAZARD_RELAY_PIN, LOW);
    digitalWrite(VIBRATION_PIN, LOW);
    noTone(BUZZER_PIN);

  } else if (risk == "LOW") {
    digitalWrite(GREEN_LED_PIN, LOW);
    if (now - lastBlinkToggle >= BLINK_SLOW_MS) {
      blinkState = !blinkState;
      lastBlinkToggle = now;
    }
    digitalWrite(AMBER_LED_PIN, blinkState ? HIGH : LOW);
    digitalWrite(RED_LED_PIN, LOW);
    digitalWrite(HAZARD_RELAY_PIN, LOW);
    digitalWrite(VIBRATION_PIN, LOW);
    noTone(BUZZER_PIN);  // LOW is audio-via-Pi-TTS only, no buzzer

  } else if (risk == "MEDIUM") {
    digitalWrite(GREEN_LED_PIN, LOW);
    digitalWrite(AMBER_LED_PIN, HIGH);
    digitalWrite(RED_LED_PIN, LOW);
    digitalWrite(HAZARD_RELAY_PIN, LOW);
    digitalWrite(VIBRATION_PIN, HIGH);
    if (now - lastBeepToggle >= MEDIUM_BEEP_MS) {
      beepState = !beepState;
      lastBeepToggle = now;
    }
    if (beepState) tone(BUZZER_PIN, 1500); else noTone(BUZZER_PIN);

  } else {  // HIGH, and the link-failure fallback in loop()
    digitalWrite(GREEN_LED_PIN, LOW);
    digitalWrite(AMBER_LED_PIN, LOW);
    if (now - lastBlinkToggle >= BLINK_FAST_MS) {
      blinkState = !blinkState;
      lastBlinkToggle = now;
    }
    digitalWrite(RED_LED_PIN, blinkState ? HIGH : LOW);
    digitalWrite(HAZARD_RELAY_PIN, blinkState ? HIGH : LOW);  // mimics hazard flasher
    digitalWrite(VIBRATION_PIN, HIGH);
    tone(BUZZER_PIN, 2500);  // continuous urgent tone
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(VIBRATION_PIN, OUTPUT);
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(AMBER_LED_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(HAZARD_RELAY_PIN, OUTPUT);
  pinMode(BT_STATUS_LED, OUTPUT);
  setAllOff();

  SerialBT.begin("DriverGuardian_ESP32");  // Bluetooth name the Pi pairs with
  Serial.println("Bluetooth SPP started as 'DriverGuardian_ESP32' - waiting for the Pi...");
  lastMessageAt = millis();
}

void loop() {
  digitalWrite(BT_STATUS_LED, SerialBT.hasClient() ? HIGH : LOW);

  // ---- Parse one line at a time as bytes arrive ----
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
          if (risk != lastRisk || reasonCase != lastCase) {
            Serial.printf("State: %s (case=%s)\n", risk.c_str(), reasonCase.c_str());
          }
          lastRisk = risk;
          lastCase = reasonCase;
          lastMessageAt = millis();
          linkFailed = false;
        }
      }
      buf = "";
    } else if (c != '\r') {
      buf += c;
      if (buf.length() > 64) buf = "";  // guard against a corrupted/unterminated line
    }
  }

  // ---- Case 8: Bluetooth Failure -> HIGH -> Safe stop mode ----
  // No message in BT_TIMEOUT_MS -> don't trust the last known state, fail
  // safe independently of the Pi.
  if (millis() - lastMessageAt > BT_TIMEOUT_MS) {
    if (!linkFailed) {
      Serial.println("Bluetooth link lost - entering fail-safe HIGH state.");
      linkFailed = true;
    }
    applyState("HIGH", "BLUETOOTH_FAILURE");
  } else {
    applyState(lastRisk, lastCase);
  }
}

// ============================================================
// DriverGuardian - Arduino Uno: cabin air sensors
// ============================================================
// Reads the two gas sensors and reports them to the Raspberry Pi over the
// USB cable (the same cable powers the Uno). Display and recording only:
// the Pi shows these values on the dashboard and saves them with the
// session; they do not change the risk level.
//
//   MQ-3  alcohol            AO -> A0
//   MQ-2  smoke / LPG / gas  AO -> A1
//   both: VCC -> 5V, GND -> GND (the heaters draw ~150 mA each, which the
//   Pi's USB port supplies; use a powered hub if the Uno browns out)
//
// Protocol (115200 baud, one line every REPORT_INTERVAL_MS):
//   SEN,mq3=<0-1023>,mq2=<0-1023>,warm=<0|1>,up=<seconds since power-on>
// The Pi can ask "ID?" and the Uno answers "DGUNO,1" - so the Pi finds the
// right USB port even when the ESP32 is plugged in too.
//
// MQ sensors need their heater warm before readings mean anything: about
// 2 minutes after power-on (and 24-48 h "burn-in" the very first time a new
// sensor is used). Until then warm=0 and the dashboard says so.
//
// Raw values are not ppm: turning them into a concentration needs a
// calibration against a known gas. The Pi reports them relative to the
// clean-air reading taken right after warm-up.

const int MQ3_PIN = A0;
const int MQ2_PIN = A1;

const unsigned long REPORT_INTERVAL_MS = 200;     // 5 reports per second
const unsigned long WARMUP_MS = 120000UL;         // 2 minutes of heater warm-up
const float SMOOTHING = 0.2;                      // exponential moving average weight

float mq3Avg = -1, mq2Avg = -1;
unsigned long lastReport = 0;
String rx;

void setup() {
  Serial.begin(115200);
  pinMode(MQ3_PIN, INPUT);
  pinMode(MQ2_PIN, INPUT);
  Serial.println("DGUNO,1");                      // hello after a reset
}

void handleCommand(String cmd) {
  cmd.trim();
  if (cmd == "ID?") Serial.println("DGUNO,1");
}

void loop() {
  // commands from the Pi (non-blocking)
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { handleCommand(rx); rx = ""; }
    else if (c != '\r' && rx.length() < 32) rx += c;
  }

  unsigned long now = millis();
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

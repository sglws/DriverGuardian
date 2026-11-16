// Latency benchmark echo sketch - pair with tools/bt_latency_benchmark.py.
// Flash this INSTEAD of DriverGuardian_ESP32 for the measurement, then
// reflash the real firmware afterwards. Same ESP32, so same MAC address -
// the benchmark's --mac default still applies, only the advertised name
// differs.
//
// Echoes each '\n'-terminated line straight back, with "\r\n" appended
// (the Pi strips it). Built to add as little turnaround time as possible,
// since anything spent here is counted as link latency:
//   - Reads byte by byte instead of readStringUntil('\n'), which blocks
//     for up to its 1000 ms stream timeout if a line arrives split across
//     Bluetooth packets - that wait would show up as a fake latency spike.
//   - Uses a fixed buffer instead of a heap String per line, so allocation
//     time doesn't add jitter to the measurement.
//   - Sends each reply in a single write(), so it isn't split across two
//     packets (which println(String) can cause).
#include "BluetoothSerial.h"

BluetoothSerial SerialBT;

const size_t MAX_LINE = 64;          // longest payload is "PING_<n>", well under this
char lineBuf[MAX_LINE + 2];          // +2 for the "\r\n" appended on reply
size_t lineLen = 0;
bool overflowed = false;

void setup() {
  Serial.begin(115200);
  SerialBT.begin("ESP32_Latency_Test"); // Bluetooth device name
}

void loop() {
  while (SerialBT.available()) {
    char c = SerialBT.read();

    if (c == '\n') {
      // Echo the exact line back immediately, in one write. Empty and
      // overlong lines are dropped - the Pi counts those as lost.
      if (!overflowed && lineLen > 0) {
        lineBuf[lineLen++] = '\r';
        lineBuf[lineLen++] = '\n';
        SerialBT.write((const uint8_t *)lineBuf, lineLen);
      }
      lineLen = 0;
      overflowed = false;
    }
    else if (c != '\r') {
      if (lineLen < MAX_LINE) {
        lineBuf[lineLen++] = c;
      } else {
        overflowed = true;           // discard the rest of this line
      }
    }
  }
}

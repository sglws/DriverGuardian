"""
arduino.py
----------
The Arduino Uno with the cabin air sensors - MQ-3 (alcohol) and MQ-2
(smoke / gas) - on a USB cable. Sketch: arduino/DriverGuardian_Uno.
Display and recording only: nothing here changes the risk level.

Wire protocol (115200 baud, ~5 lines a second from the Uno):
    SEN,mq3=<0-1023>,mq2=<0-1023>,warm=<0|1>,up=<seconds since power-on>
The Pi asks "ID?" and the Uno answers "DGUNO,1" (it also says so after a
reset).

Never blocks the main loop - the same pattern as the ESP32 link
(alerts.Esp32Link): the port is non-blocking, each poll() does at most one
cheap step, and a lost cable is searched for again on a cooldown.

Finding the port: ARDUINO_PORT = "auto" tries USB serial ports from Arduino
or the CH340 chip used on most Uno clones, asks each "ID?" and keeps the one
that answers. If the ESP32 is also plugged into the Pi by USB, set
ARDUINO_PORT to the Uno's fixed path instead (ls /dev/serial/by-id/), so
the search never opens - and possibly resets - the ESP32.

MQ readings are raw ADC values, not ppm (a concentration needs calibration
against a known gas). They are reported relative to the clean-air reading
taken in the first seconds after the heaters have warmed up.
"""

import time

from app import config

try:
    import serial
    from serial.tools import list_ports
except ImportError:          # pyserial missing: the link reports "unsupported"
    serial = None

_VIDS = {0x2341, 0x2A03, 0x1A86}   # Arduino, Arduino.org, WCH CH340/CH341 (Uno clones)
PROBE_SEC = 3.0        # an Uno reboots when its port opens; its hello comes ~2 s later
RETRY_SEC = 5.0        # wait before searching again after no Uno was found
STALE_SEC = 5.0        # connected but silent this long -> treat as unplugged
BASELINE_SEC = 10.0    # clean-air reference: the first 10 s after warm-up
ADC_VOLTS = 5.0 / 1023


class UnoLink:
    def __init__(self):
        self._ser = None
        self._probe = None             # (serial, path, deadline, next "ID?" time)
        self._candidates = []
        self._retry_at = 0.0
        self._rx = b""
        self.port = None
        self.reading, self.reading_at = None, None
        self._base_samples = {"mq3": [], "mq2": []}
        self._base_started = None
        self.baseline = None
        if config.ARDUINO_ENABLED and serial is None:
            print("[UNO] pyserial is not installed - the cabin sensors are off (pip install pyserial)")

    # ------------------------------------------------------------ status

    @property
    def status(self) -> str:
        if not config.ARDUINO_ENABLED:
            return "disabled"
        if serial is None:
            return "unsupported"
        return "connected" if self._ser is not None else "searching"

    def state(self, now: float):
        """Latest reading for the dashboard, or None."""
        r = self.reading
        if self._ser is None or r is None or now - self.reading_at > STALE_SEC:
            return None
        base = self.baseline
        rel = lambda k: round(r[k] / base[k], 2) if base and base[k] > 0 else None
        return {
            "mq3": r["mq3"], "mq2": r["mq2"],
            "mq3_v": round(r["mq3"] * ADC_VOLTS, 2), "mq2_v": round(r["mq2"] * ADC_VOLTS, 2),
            "mq3_rel": rel("mq3"), "mq2_rel": rel("mq2"),
            "warm": r["warm"], "warmup_left_s": max(0, config.ARDUINO_WARMUP_SEC - r["up"]) if not r["warm"] else 0,
            "baseline": dict(base) if base else None,
            "age_s": round(now - self.reading_at, 2), "port": self.port,
        }

    # ------------------------------------------------------------ main loop

    def poll(self, now: float):
        """Call every frame. Never blocks."""
        if not config.ARDUINO_ENABLED or serial is None:
            return
        if self._ser is not None:
            self._read(now)
        elif self._probe is not None:
            self._check_probe(now)
        elif now >= self._retry_at:
            if not self._candidates:
                self._candidates = self._list_ports()
            if self._candidates:
                self._start_probe(self._candidates.pop(0), now)
            else:
                self._retry_at = now + RETRY_SEC

    def close(self):
        for s in (self._ser, self._probe[0] if self._probe else None):
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
        self._ser = self._probe = None

    # ------------------------------------------------------------ finding the Uno

    @staticmethod
    def _list_ports():
        if config.ARDUINO_PORT != "auto":
            return [config.ARDUINO_PORT]
        try:
            return [p.device for p in list_ports.comports() if p.vid in _VIDS]
        except Exception:
            return []

    def _open(self, path):
        s = serial.Serial()
        s.port, s.baudrate, s.timeout, s.write_timeout = path, config.ARDUINO_BAUD, 0, 0
        s.dtr = s.rts = False          # don't pulse the reset lines while opening
        s.open()
        return s

    def _start_probe(self, path, now):
        try:
            s = self._open(path)
        except Exception as e:
            if config.ARDUINO_PORT != "auto":
                print(f"[UNO] cannot open {path}: {e}")
            self._retry_at = now + (0 if self._candidates else RETRY_SEC)
            return
        self._rx = b""
        self._probe = (s, path, now + PROBE_SEC, now)

    def _check_probe(self, now):
        s, path, deadline, next_ask = self._probe
        try:
            if now >= next_ask:
                s.write(b"ID?\n")
                self._probe = (s, path, deadline, now + 0.5)
            n = s.in_waiting
            if n:
                self._rx += s.read(n)
        except Exception:
            self._rx = b"\n"
        if b"DGUNO" in self._rx:
            self._ser, self._probe, self.port = s, None, path
            self._rx = self._rx[self._rx.rindex(b"DGUNO"):]
            self._rx = self._rx[self._rx.find(b"\n") + 1:] if b"\n" in self._rx else b""
            self.reading = None
            print(f"[UNO] cabin sensors connected on {path}")
            return
        if now >= deadline or self._rx == b"\n":
            try:
                s.close()
            except Exception:
                pass
            self._probe = None
            if not self._candidates:
                self._retry_at = now + RETRY_SEC

    # ------------------------------------------------------------ reading

    def _lost(self, now, why):
        print(f"[UNO] lost the cabin sensors ({why}) - searching again")
        try:
            self._ser.close()
        except Exception:
            pass
        self._ser, self.reading = None, None
        self._retry_at = now + 1.0

    def _read(self, now):
        try:
            n = self._ser.in_waiting
            data = self._ser.read(n) if n else b""
        except Exception as e:
            self._lost(now, e)
            return
        if not data:
            if self.reading_at is not None and now - self.reading_at > STALE_SEC:
                self._lost(now, f"silent for {STALE_SEC:.0f} s")
            return
        self._rx += data
        *lines, self._rx = self._rx.split(b"\n")
        self._rx = self._rx[-256:]
        for raw in lines[-10:]:
            r = parse_line(raw)
            if r is None:
                continue
            self.reading, self.reading_at = r, now
            self._track_baseline(r, now)

    def _track_baseline(self, r, now):
        if not r["warm"]:                          # still heating (or the Uno restarted)
            self._base_samples = {"mq3": [], "mq2": []}
            self._base_started, self.baseline = None, None
            return
        if self.baseline is not None:
            return
        if self._base_started is None:
            self._base_started = now
        for k in ("mq3", "mq2"):
            self._base_samples[k].append(r[k])
        if now - self._base_started >= BASELINE_SEC:
            self.baseline = {k: sum(v) / len(v) for k, v in self._base_samples.items() if v}
            print(f"[UNO] clean-air reference: MQ-3 {self.baseline['mq3']:.0f}, MQ-2 {self.baseline['mq2']:.0f}")


def parse_line(raw: bytes):
    """'SEN,mq3=412,mq2=233,warm=1,up=140' -> dict, or None."""
    text = raw.decode("ascii", errors="replace").strip()
    if not text.startswith("SEN,"):
        return None
    try:
        kv = dict(part.split("=", 1) for part in text[4:].split(","))
        return {"mq3": int(kv["mq3"]), "mq2": int(kv["mq2"]), "warm": kv["warm"] == "1", "up": int(kv["up"])}
    except (ValueError, KeyError):
        return None

"""
arduino.py
----------
The Arduino Uno with the cabin air sensors - MQ-3 (alcohol) and MQ-2
(smoke / gas) - on a USB cable. Sketch: arduino/DriverGuardian_Uno.
This module only reads them; the risk engine uses the readings for the
alcohol check before the drive (MQ-3) and for smoking (MQ-2).

Wire protocol (115200 baud, ~5 lines a second from the Uno):
    SEN,mq3=<0-1023>,mq2=<0-1023>,warm=<0|1>,up=<seconds since power-on>
The Pi asks "ID?" and the Uno answers "DGUNO,1" (it also says so after a
reset). "1" sets the Uno's pin 6 (BTS7960 fan) for a 3 s burst - sent when
the driver has been asleep (eyes closed) for 3 s (ARDUINO_FAN_SLEEP_SEC). Other lines from the Uno
are ignored.

Never blocks the main loop - the same pattern as the ESP32 link
(alerts.Esp32Link): the port is non-blocking, each poll() does at most one
cheap step, and a lost cable is searched for again on a cooldown.

Finding the port: ARDUINO_PORT = "auto" tries USB serial ports from Arduino
or the CH340 chip used on most Uno clones, asks each "ID?" and keeps the one
that answers. If the ESP32 is also plugged into the Pi by USB, set
ARDUINO_PORT to the Uno's fixed path instead (ls /dev/serial/by-id/), so
the search never opens - and possibly resets - the ESP32.

MQ readings are raw ADC values, not ppm (a concentration needs calibration
against a known gas). They are reported relative to a clean-air reference:
the average of the first AIR_REF_INIT_SEC once the heaters are warm, which
then follows clean air (see AIR_REF_* in config.py).
"""

import os
import time

from app import config

try:
    import serial
    from serial.tools import list_ports
except ImportError:          # pyserial missing: the link reports "unsupported"
    serial = None

# Arduino, Arduino.org, WCH CH340/CH341, FTDI, Prolific (Uno and its clones)
_VIDS = {0x2341, 0x2A03, 0x1A86, 0x0403, 0x067B}
PROBE_SEC = 3.0        # an Uno reboots when its port opens; its hello comes ~2 s later
RETRY_SEC = 5.0        # wait before searching again after no Uno was found
STALE_SEC = 5.0        # connected but silent this long -> treat as unplugged
ADC_VOLTS = 5.0 / 1023


def powered_since(path, now):
    """When the Uno - and the MQ heaters on its 5 V - got power, as a
    time.monotonic() value: when its USB serial port appeared (the device
    file's ctime), but never before the computer booted, in case the clock
    was set after boot (no RTC battery) and the file looks older than it is.
    Opening the port resets the Uno, so its own up-time can't tell."""
    try:
        age = time.time() - os.stat(os.path.realpath(path)).st_ctime
    except OSError:
        return now
    if hasattr(time, "CLOCK_BOOTTIME"):
        age = min(age, time.clock_gettime(time.CLOCK_BOOTTIME))
    return now - max(0.0, age)


class UnoLink:
    def __init__(self):
        self._ser = None
        self._probe = None             # (serial, path, deadline, next "ID?" time)
        self._candidates = []
        self._retry_at = 0.0
        self._rx = b""
        self.port = None
        self.reading, self.reading_at = None, None
        self.powered_since = None      # when the Uno got power (time.monotonic())
        self._base_samples = {"mq3": [], "mq2": []}
        self._base_started = self._base_at = None
        self.baseline = None
        self.note = ""                 # why it isn't connected, for the dashboard
        if config.ARDUINO_ENABLED and serial is None:
            self._set_note("pyserial is not installed: pip install -r requirements.txt")

    def _set_note(self, text):
        if text != self.note:
            self.note = text
            if text:
                print(f"[UNO] {text}")

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
            "warm": self._warm(now), "warmup_left_s": round(self._warmup_left(now)),
            "baseline": {k: round(v, 1) for k, v in base.items()} if base else None,
            "limits": {"mq3": config.ALCOHOL_RATIO, "mq2": config.SMOKE_RATIO_ON},
            "age_s": round(now - self.reading_at, 2), "port": self.port,
        }

    def _warmup_left(self, now):
        if self.powered_since is None:
            return config.ARDUINO_WARMUP_SEC
        return max(0.0, config.ARDUINO_WARMUP_SEC - (now - self.powered_since))

    def _warm(self, now):
        return self.powered_since is not None and self._warmup_left(now) == 0

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

    def _list_ports(self):
        if config.ARDUINO_PORT != "auto":
            return [config.ARDUINO_PORT]
        try:
            ports = list(list_ports.comports())
        except Exception:
            ports = []
        found = [p.device for p in ports if p.vid in _VIDS or p.device.startswith("/dev/ttyACM")]
        if not found:
            seen = ", ".join(f"{p.device} ({p.vid:04x}:{p.pid:04x})" if p.vid else p.device for p in ports if "ttyAMA" not in p.device and "ttyS" not in p.device)
            self._set_note(f"no Arduino on USB{f' (seen: {seen})' if seen else ''} - check the cable; run tools/check_uno.py")
        return found

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
            msg = str(e)
            if "ermission" in msg:
                self._set_note(f"no permission for {path}: run 'sudo usermod -aG dialout $USER', then log out and in")
            elif "busy" in msg.lower():
                self._set_note(f"{path} is in use by another program (Arduino Serial Monitor? screen?) - close it")
            else:
                self._set_note(f"cannot open {path}: {msg}")
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
            self.note = ""
            self.powered_since = powered_since(path, now)
            self.baseline = self._base_started = None
            left = self._warmup_left(now)
            print(f"[UNO] cabin sensors connected on {path}"
                  + (f" - MQ heaters warming up, {left:.0f} s left" if left else " - MQ heaters already warm"))
            return
        if now >= deadline or self._rx == b"\n":
            heard = self._rx.decode("ascii", "replace").strip()[-60:]
            self._set_note(f"{path} opened but the Uno didn't answer"
                           + (f" (it said: {heard!r} - wrong sketch or baud rate?)" if heard else " - is the DriverGuardian sketch flashed?"))
            try:
                s.close()
            except Exception:
                pass
            self._probe = None
            if not self._candidates:
                self._retry_at = now + RETRY_SEC

    # ------------------------------------------------------------ reading

    def fan(self) -> bool:
        """Pin 6 on the Uno for a 3 s burst ("1"). Never blocks; False if not connected."""
        if self._ser is None:
            return False
        try:
            self._ser.write(b"1\n")
            return True
        except Exception:
            return False

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
        if not self._warm(now):                    # heaters still warming up
            self._base_samples = {"mq3": [], "mq2": []}
            self._base_started, self.baseline = None, None
            return
        if self.baseline is None:                  # first reference: a short average
            if self._base_started is None:
                self._base_started = now
                self._base_samples = {"mq3": [], "mq2": []}
            for k in ("mq3", "mq2"):
                self._base_samples[k].append(r[k])
            if now - self._base_started >= config.AIR_REF_INIT_SEC:
                self.baseline = {k: sum(v) / len(v) for k, v in self._base_samples.items() if v}
                self._base_at = now
                print(f"[UNO] clean-air reference: MQ-3 {self.baseline['mq3']:.0f}, MQ-2 {self.baseline['mq2']:.0f}")
                for k, limit, name in (("mq3", config.ALCOHOL_RAW_LIMIT, "ALCOHOL_RAW_LIMIT"),
                                       ("mq2", config.SMOKE_RAW_LIMIT, "SMOKE_RAW_LIMIT")):
                    if limit is not None and self.baseline[k] >= 0.8 * limit:
                        print(f"[UNO] WARNING: the {k.upper()} reference ({self.baseline[k]:.0f}) is close to "
                              f"{name} ({limit}) - gas in the air now, or set {name} higher in config.py")
            return
        # Then follow clean air: down quickly, up slowly, frozen while a gas is present.
        dt, self._base_at = now - self._base_at, now
        for k in ("mq3", "mq2"):
            b, x = self.baseline[k], r[k]
            if x < b:
                tau = config.AIR_REF_DOWN_SEC
            elif x < b * config.AIR_REF_FREEZE_RATIO:
                tau = config.AIR_REF_UP_SEC
            else:
                continue
            self.baseline[k] = b + min(1.0, dt / tau) * (x - b)


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

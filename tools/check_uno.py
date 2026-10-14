"""Find out why the Pi doesn't see the Arduino Uno (cabin air sensors).

Run on the Pi with the Uno plugged in by USB - and the DriverGuardian app
stopped (only one program can use the port):
    python tools/check_uno.py              # search every USB serial port
    python tools/check_uno.py /dev/ttyUSB0 # check one port
It lists the serial ports, checks permissions, opens each likely port, and
prints what the board says for a few seconds.
"""
import glob
import grp
import os
import shutil
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial is not installed in this Python. Run: pip install -r requirements.txt\n"
             f"(this is {sys.executable} - run the app and this check with the same Python)")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import config  # noqa: E402
from app.arduino import _VIDS, parse_line  # noqa: E402


def main():
    print(f"Python: {sys.executable}   pyserial {serial.__version__}")
    print(f"ARDUINO_ENABLED = {config.ARDUINO_ENABLED}, ARDUINO_PORT = {config.ARDUINO_PORT!r}, baud {config.ARDUINO_BAUD}\n")

    ports = list(list_ports.comports())
    print("Serial ports:")
    for p in ports:
        vid = f"{p.vid:04x}:{p.pid:04x}" if p.vid else "no USB id"
        mark = "  <- looks like an Arduino" if (p.vid in _VIDS or p.device.startswith("/dev/ttyACM")) else ""
        print(f"  {p.device:16s} {vid:10s} {p.description}{mark}")
    if not ports:
        print("  (none)")
    by_id = glob.glob("/dev/serial/by-id/*")
    if by_id:
        print("Fixed paths (/dev/serial/by-id):")
        for b in by_id:
            print(f"  {b} -> {os.path.realpath(b)}")

    if sys.platform.startswith("linux"):
        groups = {grp.getgrgid(g).gr_name for g in os.getgroups()}
        if "dialout" not in groups:
            print("\n!! You are not in the 'dialout' group, so you may not open serial ports.\n"
                  "   Fix: sudo usermod -aG dialout $USER   then log out and back in (or reboot).")
        if shutil.which("brltty"):
            print("\n!! 'brltty' (braille display support) is installed. It is known to grab CH340\n"
                  "   USB-serial chips, so a clone Uno never appears as /dev/ttyUSB0.\n"
                  "   If no ttyUSB/ttyACM port shows up above: sudo apt remove brltty, then replug the Uno.")

    if len(sys.argv) > 1:
        targets = [sys.argv[1]]
    else:
        targets = [p.device for p in ports if p.vid in _VIDS or p.device.startswith("/dev/ttyACM")]
    if not targets:
        sys.exit("\nNo Arduino-like USB serial port found. Check the cable (some USB cables carry power only),\n"
                 "try another USB port, and look at 'dmesg | tail' right after plugging the Uno in.")

    for path in targets:
        print(f"\n--- {path} ---")
        if not os.access(path, os.R_OK | os.W_OK):
            print("  no read/write permission (see 'dialout' above)")
        try:
            s = serial.Serial(path, config.ARDUINO_BAUD, timeout=0.2)
        except Exception as e:
            print(f"  cannot open: {e}")
            continue
        print("  opened - the Uno restarts now; listening for 5 s...")
        t0, buf, lines, got_id, got_sen = time.monotonic(), b"", 0, False, None
        asked = 0.0
        while time.monotonic() - t0 < 5:
            if time.monotonic() - asked > 1.0:
                s.write(b"ID?\n"); asked = time.monotonic()
            buf += s.read(256)
            *done, buf = buf.split(b"\n")
            for raw in done:
                text = raw.decode("ascii", "replace").strip()
                if not text:
                    continue
                lines += 1
                if lines <= 8:
                    print(f"  < {text}")
                got_id |= "DGUNO" in text
                got_sen = parse_line(raw) or got_sen
        s.close()
        if got_id and got_sen:
            print(f"  OK: DriverGuardian Uno, MQ-3 {got_sen['mq3']}, MQ-2 {got_sen['mq2']}, "
                  f"{'warm' if got_sen['warm'] else 'warming up'}. The app should find it on {path}.")
            if config.ARDUINO_PORT not in ("auto", path):
                print(f"  !! but ARDUINO_PORT is set to {config.ARDUINO_PORT!r} - set it to 'auto' or {path!r}")
        elif lines:
            print("  The board talks, but not the DriverGuardian way: flash arduino/DriverGuardian_Uno, 115200 baud.")
        else:
            print("  Silence. Wrong port, wrong baud rate, the sketch isn't flashed, or another program holds the port.")


if __name__ == "__main__":
    main()

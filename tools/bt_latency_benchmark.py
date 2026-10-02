"""
bt_latency_benchmark.py
-----------------------
Round-trip latency benchmark for the Pi <-> ESP32 Bluetooth SPP link,
for report measurements.

Pair it with the esp32/latency_echo/latency_echo.ino sketch (echoes each line straight back).

IMPORTANT - transport choice:
  The app (app/alerts.py) talks to the ESP32 over a RAW
  AF_BLUETOOTH/BTPROTO_RFCOMM socket to the MAC address - NOT via a
  `rfcomm bind` /dev/rfcommX device file, which alerts.py's docstring notes
  "has proven unreliable on some BlueZ versions". So `--transport socket`
  (the default) is what reproduces production. `--transport serial` is kept
  only for comparing the two paths.

Stop the app first - the ESP32 accepts only one Bluetooth connection.

Usage on the Pi:
    python3 tools/bt_latency_benchmark.py                      # matches production
    python3 tools/bt_latency_benchmark.py --audio --label "wifi + speaker playing"
    python3 tools/bt_latency_benchmark.py --interval 0.05      # stress cadence
    python3 tools/bt_latency_benchmark.py --transport serial --port /dev/rfcomm0

--audio keeps the default audio output (e.g. the Bluetooth speaker) playing
for the whole run: the Pi's Bluetooth radio is shared between the speaker and
the ESP32 link (and with Wi-Fi on the Pi's combo chip), so this is the
realistic worst case. Requirement: round trip p99 <= 50 ms, max <= 100 ms.
"""

import argparse
import contextlib
import csv
import glob
import math
import os
import shutil
import signal
import socket
import struct
import subprocess
import wave
import statistics
import sys
import time

DEFAULT_MAC = "08:B6:1F:3B:1A:AA"   # keep in sync with config.ESP32_MAC_ADDRESS
DEFAULT_RFCOMM_PORT = 1


class SocketLink:
    """Raw RFCOMM socket - the same transport app/alerts.py uses."""

    def __init__(self, mac, channel, timeout):
        self.sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM,
                                  socket.BTPROTO_RFCOMM)
        # No timeout during connect: a Classic Bluetooth RFCOMM handshake can
        # legitimately take seconds, and a short timeout cuts it off mid-
        # negotiation (surfaces as "[Errno 52] Invalid exchange"). Same
        # reasoning as alerts.py.
        self.sock.connect((mac, channel))
        self._timeout = timeout
        self.sock.settimeout(timeout)
        self._buf = b""

    def drain(self):
        """Discard anything still queued, so a late reply from a previous
        iteration can't be misread as this iteration's reply. Without this,
        a single timeout desyncs every subsequent sample."""
        self.sock.settimeout(0)
        try:
            while True:
                if not self.sock.recv(4096):
                    break
        except (BlockingIOError, socket.error):
            pass
        finally:
            self.sock.settimeout(self._timeout)
        self._buf = b""

    def settimeout(self, t):
        self._timeout = t
        self.sock.settimeout(t)

    def write(self, data):
        self.sock.sendall(data)      # sendall blocks until handed to the stack

    def readline(self):
        while b"\n" not in self._buf:
            chunk = self.sock.recv(256)
            if not chunk:
                return b""
            self._buf += chunk
        line, _, self._buf = self._buf.partition(b"\n")
        return line + b"\n"

    def close(self):
        with contextlib.suppress(Exception):
            self.sock.close()


class SerialLink:
    """/dev/rfcommX device file - NOT what the app uses; for comparison only."""

    def __init__(self, port, baud, timeout):
        import serial   # imported lazily so the socket path needs no pyserial
        self.ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(2)   # let the link settle

    def drain(self):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

    def settimeout(self, t):
        self.ser.timeout = t

    def write(self, data):
        self.ser.write(data)
        self.ser.flush()             # block until actually pushed out

    def readline(self):
        return self.ser.readline()

    def close(self):
        with contextlib.suppress(Exception):
            self.ser.close()


def run(link, samples, warmup, interval, timeout):
    link.settimeout(timeout)
    rtts, mismatched, timed_out = [], 0, 0
    total = samples + warmup

    for i in range(total):
        # Clear any stale reply BEFORE timing, so one bad iteration can't
        # cascade into every following one.
        link.drain()

        payload = f"PING_{i}\n".encode("utf-8")
        t0 = time.perf_counter()
        link.write(payload)
        try:
            raw = link.readline()
        except socket.timeout:
            raw = b""
        t1 = time.perf_counter()

        response = raw.decode("utf-8", errors="replace").strip()
        expected = f"PING_{i}"

        if not response:
            timed_out += 1
        elif response != expected:
            mismatched += 1
        elif i >= warmup:
            # Warm-up samples are discarded: the first exchanges after a
            # connection come up carry ramp-up cost and aren't representative.
            rtts.append((t1 - t0) * 1000.0)

        if interval:
            time.sleep(interval)

    return rtts, mismatched, timed_out, total


class AudioLoad:
    """Keeps the default audio output playing (a loop of an alert prompt, or
    a tone) for the duration of the benchmark."""

    def __init__(self):
        player = shutil.which("pw-play") or shutil.which("paplay") or shutil.which("aplay") or shutil.which("afplay")
        if not player:
            raise RuntimeError("no audio player found (pw-play / paplay / aplay / afplay)")
        here = os.path.dirname(os.path.abspath(__file__))
        prompts = sorted(glob.glob(os.path.join(here, "..", "assets", "voice_cache", "*.wav")))
        self.wav = prompts[0] if prompts else self._tone()
        self.proc = subprocess.Popen(
            ["sh", "-c", f'while true; do "{player}" "{self.wav}"; done'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.desc = f"{os.path.basename(player)} looping {os.path.basename(self.wav)}"

    @staticmethod
    def _tone(path="/tmp/bt_bench_tone.wav", sec=3.0, rate=22050):
        with wave.open(path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
            w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate)))
                                   for i in range(int(sec * rate))))
        return path

    def stop(self):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(self.proc.pid, signal.SIGTERM)


def report(rtts, mismatched, timed_out, total, warmup, interval, transport, csv_path,
           conditions="", req_p99=50.0, req_max=100.0):
    if not rtts:
        print("No successful round trips - nothing to report.", file=sys.stderr)
        return 1

    rtts_sorted = sorted(rtts)

    def pct(p):
        # Nearest-rank: unambiguous and stable for report figures, unlike
        # interpolating quantiles on a skewed latency distribution.
        k = max(1, int(round(p / 100.0 * len(rtts_sorted))))
        return rtts_sorted[k - 1]

    print("\n--- Bluetooth SPP Round-Trip Latency ---")
    print(f"Transport:          {transport}")
    if conditions:
        print(f"Conditions:         {conditions}")
    print(f"Ping interval:      {interval * 1000:.0f} ms")
    print(f"Samples (measured): {len(rtts)}  (+{warmup} warm-up discarded, {total} sent)")
    print(f"Timeouts:           {timed_out}")
    print(f"Mismatched replies: {mismatched}")
    print(f"Min:                {min(rtts):.2f} ms")
    print(f"Median (p50):       {statistics.median(rtts):.2f} ms")
    print(f"Mean:               {statistics.mean(rtts):.2f} ms")
    print(f"p95:                {pct(95):.2f} ms")
    print(f"p99:                {pct(99):.2f} ms")
    print(f"Max:                {max(rtts):.2f} ms")
    if len(rtts) > 1:
        print(f"Jitter (stdev):     {statistics.stdev(rtts):.2f} ms")
    print("\nNote: these are ROUND-TRIP times. They include the ESP32's own")
    print("receive+echo turnaround, so RTT/2 OVERSTATES one-way link latency.")
    ok_p99, ok_max = pct(99) <= req_p99, max(rtts) <= req_max
    lost = timed_out + mismatched
    print(f"\nRequirement p99 <= {req_p99:g} ms:  {pct(99):.1f} ms  {'PASS' if ok_p99 else 'FAIL'}")
    print(f"Requirement max <= {req_max:g} ms:  {max(rtts):.1f} ms  {'PASS' if ok_max else 'FAIL'}")
    if lost:
        print(f"Warning: {lost} ping(s) timed out or got a wrong reply - not included above.")

    if csv_path:
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["sample", "rtt_ms"])
            for n, v in enumerate(rtts):
                w.writerow([n, f"{v:.4f}"])
        print(f"\nRaw samples written to {csv_path} (for histogram/CDF plots).")
    return 0 if ok_p99 and ok_max else 2


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transport", choices=("socket", "serial"), default="socket",
                    help="socket = raw RFCOMM, same as the app (default); "
                         "serial = /dev/rfcommX, for comparison only")
    ap.add_argument("--mac", default=DEFAULT_MAC)
    ap.add_argument("--channel", type=int, default=DEFAULT_RFCOMM_PORT)
    ap.add_argument("--port", default="/dev/rfcomm0", help="serial transport only")
    ap.add_argument("--baud", type=int, default=115200,
                    help="serial transport only; ignored by RFCOMM (virtual port)")
    ap.add_argument("--samples", type=int, default=500)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--interval", type=float, default=0.3,
                    help="seconds between pings; default 0.3 matches the app's "
                         "ESP32_SEND_INTERVAL_SEC")
    ap.add_argument("--timeout", type=float, default=2.0)
    ap.add_argument("--csv", default="bt_latency_samples.csv",
                    help="raw per-sample output; empty string to skip")
    ap.add_argument("--audio", action="store_true",
                    help="keep the speaker playing during the run (realistic radio load)")
    ap.add_argument("--label", default="", help="free-text test conditions for the report")
    ap.add_argument("--req-p99", type=float, default=50.0, help="requirement: p99 round trip (ms)")
    ap.add_argument("--req-max", type=float, default=100.0, help="requirement: max round trip (ms)")
    args = ap.parse_args()

    try:
        if args.transport == "socket":
            link = SocketLink(args.mac, args.channel, args.timeout)
            desc = f"raw RFCOMM socket -> {args.mac} ch{args.channel}"
        else:
            link = SerialLink(args.port, args.baud, args.timeout)
            desc = f"{args.port} (device file)"
    except Exception as e:
        print(f"Could not open link: {e}", file=sys.stderr)
        print("Is the ESP32 paired, trusted and in range? For --transport serial, "
              "is rfcomm bound?", file=sys.stderr)
        return 1

    audio = None
    if args.audio:
        try:
            audio = AudioLoad()
            print(f"Audio load: {audio.desc}")
        except RuntimeError as e:
            print(f"--audio: {e}", file=sys.stderr)
            return 1
    conditions = ", ".join(x for x in (args.label, "audio playing" if audio else "") if x)
    print(f"Benchmarking {desc}: {args.samples} samples "
          f"(+{args.warmup} warm-up) at {args.interval * 1000:.0f} ms intervals...")
    try:
        rtts, mism, touts, total = run(link, args.samples, args.warmup,
                                       args.interval, args.timeout)
    finally:
        link.close()
        if audio:
            audio.stop()

    return report(rtts, mism, touts, total, args.warmup, args.interval, desc, args.csv,
                  conditions, args.req_p99, args.req_max)


if __name__ == "__main__":
    sys.exit(main())

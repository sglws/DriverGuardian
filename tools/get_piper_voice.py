"""Download a Piper voice into models/piper/ (resumes and retries on a flaky
connection). The app uses the voice named in config.VOICE_PIPER_VOICE.

Usage:
    python tools/get_piper_voice.py                       # the configured voice
    python tools/get_piper_voice.py en_US-amy-medium      # another voice

Voice names: https://huggingface.co/rhasspy/piper-voices (en/en_US/...).
Needs: pip install piper-tts
"""
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import config  # noqa: E402

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

try:   # some Python installs (e.g. python.org on macOS) ship without CA certificates
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL = ssl.create_default_context()


def url_for(voice: str, ext: str) -> str:
    lang_region, name, quality = voice.split("-", 2)      # en_US, lessac, medium
    lang = lang_region.split("_")[0]
    return f"{BASE}/{lang}/{lang_region}/{name}/{quality}/{voice}.{ext}"


def download(url: str, dest: str, attempts: int = 30):
    for attempt in range(1, attempts + 1):
        have = os.path.getsize(dest) if os.path.exists(dest) else 0
        req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
        try:
            with urllib.request.urlopen(req, timeout=30, context=_SSL) as r:
                total = have + int(r.headers.get("Content-Length", 0))
                if have and r.status != 206:      # server ignored the range: start over
                    have, total = 0, int(r.headers.get("Content-Length", 0))
                with open(dest, "ab" if have else "wb") as f:
                    while chunk := r.read(1 << 16):
                        f.write(chunk)
                        have += len(chunk)
                        print(f"\r  {os.path.basename(dest)}: {have / 1e6:5.1f} / {total / 1e6:.1f} MB", end="", flush=True)
            print()
            return
        except urllib.error.HTTPError as e:
            if e.code == 416:                     # already complete
                print(f"  {os.path.basename(dest)}: already complete")
                return
            raise
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
            print(f"\n  connection dropped ({e}) - resuming (attempt {attempt}/{attempts})")
            time.sleep(3)
    raise SystemExit(f"Download failed after {attempts} attempts: {url}")


def main():
    voice = sys.argv[1] if len(sys.argv) > 1 else config.VOICE_PIPER_VOICE
    out_dir = os.path.join(config.MODELS_DIR, "piper")
    os.makedirs(out_dir, exist_ok=True)
    print(f"Downloading Piper voice {voice} to {out_dir}")
    for ext in ("onnx.json", "onnx"):
        download(url_for(voice, ext), os.path.join(out_dir, f"{voice}.{ext}"))
    print(f"Done. Set VOICE_PIPER_VOICE = \"{voice}\" in app/config.py (if it isn't already) "
          f"and restart the app - the alert phrases re-render automatically.")


if __name__ == "__main__":
    main()

"""Renders a list of phrases with one Piper voice, loading the model only once.

Run by voice.py: python -m app.outputs.piper_render MODEL < [[text, wav_path], ...]
"""

import json
import sys
import wave

from piper import PiperVoice


def main():
    jobs = json.load(sys.stdin)
    voice = PiperVoice.load(sys.argv[1])
    for text, out_path in jobs:
        with wave.open(out_path, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)


if __name__ == "__main__":
    main()

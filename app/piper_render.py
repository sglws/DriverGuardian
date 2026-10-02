"""
piper_render.py
---------------
Renders several phrases with one Piper voice in a single process: the
voice model is loaded once (seconds on a Pi) instead of once per phrase.
Used by voice.py when the prompt cache needs (re)building - not run by hand.

stdin: JSON list of [text, output_wav_path]
argv:  path to the voice's .onnx model (its .onnx.json sits next to it)
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

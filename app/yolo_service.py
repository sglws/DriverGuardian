"""
yolo_service.py
---------------
YOLO inference in its own process - started by yolo_detector.YoloProcess,
not meant to be run by hand. Receives (frame, mouth_roi, scale) over the
inherited socket and answers with the confirmed detection state, box
coordinates scaled back to the full camera frame.

It inherits the app's lower CPU priority, CPU-core reservation and
thread-pool environment. It exits when the app closes the connection,
including when the app itself crashes or is killed.
"""

import sys
import time
from multiprocessing.connection import Connection

import cv2

cv2.setNumThreads(1)   # letterbox resize only; inference has its own pool


def main():
    conn = Connection(int(sys.argv[1]))
    from app.yolo_detector import YoloDetector, DetectionConfirmer
    detector, confirmer = YoloDetector(), DetectionConfirmer()
    conn.send({"type": "ready", "available": detector.available})
    while True:
        try:
            msg = conn.recv()
        except (EOFError, OSError):
            break
        if msg is None:
            break
        frame, mouth_roi, scale = msg
        state = confirmer.update(detector.detect(frame, mouth_roi=mouth_roi), time.monotonic())
        if scale != 1.0:
            state["raw_boxes"] = [(x1 / scale, y1 / scale, x2 / scale, y2 / scale, label, conf, counted)
                                  for x1, y1, x2, y2, label, conf, counted in state["raw_boxes"]]
        try:
            conn.send(state)
        except (EOFError, OSError):
            break


if __name__ == "__main__":
    main()

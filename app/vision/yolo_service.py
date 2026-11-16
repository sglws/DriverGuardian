"""YOLO inference process, started by yolo_detector.YoloProcess (not run by hand).

Receives (frame, mouth_roi, scale) over the inherited socket and answers with
the confirmed detections, boxes scaled back to the full camera frame. Exits
when the app closes the connection.
"""

import os
import sys
import time
from multiprocessing.connection import Connection

import cv2

cv2.setNumThreads(1)


def main():
    try:
        os.nice(19 - os.nice(0))   # lowest priority: YOLO has slack, the video loop does not
    except OSError:
        pass
    conn = Connection(int(sys.argv[1]))
    from app.vision.yolo_detector import YoloDetector, DetectionConfirmer
    detector, confirmer = YoloDetector(), DetectionConfirmer()
    conn.send({"type": "ready", "available": detector.available})
    while True:
        try:
            msg = conn.recv()
        except (EOFError, OSError):
            break
        if msg is None:
            break
        if isinstance(msg[0], str):   # ("raw", frame, roi): no confirmation filter
            _, frame, mouth_roi = msg
            raw = detector.detect(frame, mouth_roi=mouth_roi)
            reply = {"type": "raw", "result": {k: v for k, v in raw.items() if k != "raw_boxes"}}
        else:
            frame, mouth_roi, scale = msg
            reply = confirmer.update(detector.detect(frame, mouth_roi=mouth_roi), time.monotonic())
            if scale != 1.0:
                reply["raw_boxes"] = [(x1 / scale, y1 / scale, x2 / scale, y2 / scale, label, conf, counted)
                                      for x1, y1, x2, y2, label, conf, counted in reply["raw_boxes"]]
        try:
            conn.send(reply)
        except (EOFError, OSError):
            break


if __name__ == "__main__":
    main()

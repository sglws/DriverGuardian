"""
face_mesh.py
------------
Phase 3 deliverable: 468(+10 iris)-point facial landmark extraction.
"""

import mediapipe as mp


class FaceMeshWrapper:
    def __init__(self, min_detection_confidence: float = 0.4,
                 min_tracking_confidence: float = 0.4):
        self._mp_face_mesh = mp.solutions.face_mesh
        self._mp_drawing = mp.solutions.drawing_utils
        self._mp_styles = mp.solutions.drawing_styles

        self.mesh = self._mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,   # adds iris landmarks (478 total)
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self.FACEMESH_CONTOURS = self._mp_face_mesh.FACEMESH_CONTOURS

    def process(self, rgb_frame):
        """Returns a list of landmarks (x, y, z, visibility-less) or None."""
        results = self.mesh.process(rgb_frame)
        if not results.multi_face_landmarks:
            return None, None
        face_landmarks = results.multi_face_landmarks[0]
        return face_landmarks.landmark, face_landmarks  # (raw list, drawable object)

    def draw(self, frame, face_landmarks_obj):
        self._mp_drawing.draw_landmarks(
            image=frame,
            landmark_list=face_landmarks_obj,
            connections=self.FACEMESH_CONTOURS,
            landmark_drawing_spec=None,
            connection_drawing_spec=self._mp_styles.get_default_face_mesh_contours_style(),
        )

    def close(self):
        self.mesh.close()

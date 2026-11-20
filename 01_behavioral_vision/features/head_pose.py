"""
features/head_pose.py
======================
Head pose estimation via OpenCV solvePnP.

Computes pitch, yaw, roll in degrees from the driver's head orientation
relative to the camera.  Detects:
  - Gradual forward droop  (pitch increasing over time → microsleep onset)
  - Sudden nod event       (rapid large pitch change within 1–2 frames)

All functions are pure where possible; the NodDetector class holds the
minimal required state (a short timestamp deque).

Reference
---------
MediaPipe solvePnP-compatible indices used: [1, 152, 33, 263, 61, 291]
(nose tip, chin, left/right eye outer corners, left/right mouth corners).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# 3-D canonical face model (in mm, face-centric coordinate system)
# ---------------------------------------------------------------------------

MODEL_POINTS_3D = np.array([
    [ 0.0,   0.0,    0.0   ],   # Nose tip        → lm[1]
    [ 0.0,  -330.0, -65.0  ],   # Chin            → lm[152]
    [-225.0,  170.0, -135.0],   # Left eye corner → lm[33]
    [ 225.0,  170.0, -135.0],   # Right eye corner→ lm[263]
    [-150.0, -150.0, -125.0],   # Left mouth      → lm[61]
    [ 150.0, -150.0, -125.0],   # Right mouth     → lm[291]
], dtype=np.float64)

LANDMARK_INDICES_FOR_PNP = [1, 152, 33, 263, 61, 291]


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def estimate_head_pose(
    landmarks: np.ndarray,
    image_wh: tuple[int, int],
    pnp_indices: list[int] = LANDMARK_INDICES_FOR_PNP,
) -> tuple[float, float, float]:
    """
    Estimate head pitch, yaw, roll using solvePnP.

    Parameters
    ----------
    landmarks : np.ndarray
        Full landmark array shape (N, 3), normalised [0, 1].
    image_wh : tuple[int, int]
        (width, height) of the source frame.
    pnp_indices : list[int]
        Indices into ``landmarks`` for the six solvePnP anchor points.

    Returns
    -------
    pitch : float  (degrees; positive = forward droop)
    yaw   : float  (degrees; positive = face turned right)
    roll  : float  (degrees; positive = tilt clockwise)
    """
    w, h = image_wh
    image_pts = landmarks[pnp_indices, :2] * np.array([w, h], dtype=np.float64)
    image_pts = image_pts.astype(np.float64)

    # Approximate camera intrinsics (principal point at centre, focal = width)
    focal  = float(w)
    cam_matrix = np.array([
        [focal,  0,     w / 2.0],
        [0,      focal, h / 2.0],
        [0,      0,     1.0    ],
    ], dtype=np.float64)
    dist_coeffs = np.zeros((4, 1), dtype=np.float64)

    success, rvec, tvec = cv2.solvePnP(
        MODEL_POINTS_3D, image_pts, cam_matrix, dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    if not success:
        return 0.0, 0.0, 0.0

    # Convert rotation vector → rotation matrix → Euler angles
    # Use the nose-direction vector method for more intuitive angles
    rot_mat, _ = cv2.Rodrigues(rvec)

    # Project a point 1 unit forward from the nose in 3D model space
    # to get the nose-pointing direction in camera space
    nose_end_3d = np.array([[0.0, 0.0, -500.0]])
    nose_end_2d, _ = cv2.projectPoints(
        nose_end_3d, rvec, tvec, cam_matrix, dist_coeffs
    )

    # Compute pitch/yaw from the direction the nose is pointing in image coords
    nose_2d = image_pts[0]  # nose tip in 2D
    nose_end = nose_end_2d[0][0]

    dx = float(nose_end[0] - nose_2d[0])
    dy = float(nose_end[1] - nose_2d[1])

    # atan2-based angles (in degrees) — stable for frontal faces
    yaw_rad   =  np.arctan2(dx, focal)
    pitch_rad = -np.arctan2(dy, focal)

    # Convert to degrees
    pitch = float(np.degrees(pitch_rad))
    yaw   = float(np.degrees(yaw_rad))

    # Roll from rotation matrix (column x-axis tilt)
    roll = float(np.degrees(np.arctan2(rot_mat[1, 0], rot_mat[0, 0])))

    return pitch, yaw, roll


def _rotation_matrix_to_euler(R: np.ndarray) -> tuple[float, float, float]:
    """Convert 3×3 rotation matrix to Euler angles (degrees) — ZXY convention."""
    sy = np.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
    singular = sy < 1e-6
    if not singular:
        pitch = np.degrees(np.arctan2( R[2, 1], R[2, 2]))
        yaw   = np.degrees(np.arctan2(-R[2, 0], sy))
        roll  = np.degrees(np.arctan2( R[1, 0], R[0, 0]))
    else:
        pitch = np.degrees(np.arctan2(-R[1, 2], R[1, 1]))
        yaw   = np.degrees(np.arctan2(-R[2, 0], sy))
        roll  = 0.0
    return pitch, yaw, roll




# ---------------------------------------------------------------------------
# Nod detector (stateful, minimal)
# ---------------------------------------------------------------------------

@dataclass
class NodDetector:
    """
    Detects sudden forward head-nod events (micro-sleep drop).

    A nod is detected when pitch changes by more than ``nod_threshold_deg``
    within ``nod_window_frames`` consecutive frames and the pitch returns.

    Parameters
    ----------
    nod_threshold_deg : float
        Minimum pitch change (degrees) in the short window to fire.
    nod_window_frames : int
        Number of frames over which the pitch delta is measured.
    """
    nod_threshold_deg: float = 15.0
    nod_window_frames: int   = 5

    _pitch_history: deque = field(
        default_factory=lambda: deque(maxlen=10), init=False, repr=False
    )

    def update(self, pitch: float) -> bool:
        """
        Feed one pitch sample.

        Returns
        -------
        bool
            True if a sudden nod event is detected this frame.
        """
        self._pitch_history.append(pitch)
        if len(self._pitch_history) < self.nod_window_frames:
            return False
        window = list(self._pitch_history)[-self.nod_window_frames:]
        delta  = max(window) - min(window)
        return delta >= self.nod_threshold_deg

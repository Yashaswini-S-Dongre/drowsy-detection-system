"""
features/gaze.py
=================
Iris-based gaze deviation estimation and off-road gaze ratio tracking.

Uses MediaPipe iris landmarks (indices 468 and 473) to compute gaze direction
as yaw/pitch offsets relative to the face centre.  The off-road ratio is
a sliding window fraction of frames where gaze deviates beyond a threshold.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------------------
# Pure gaze functions
# ---------------------------------------------------------------------------

def compute_gaze(
    landmarks: np.ndarray,
    left_iris_idx:  int = 468,
    right_iris_idx: int = 473,
    left_eye_corner_idxs:  tuple[int, int] = (33, 133),
    right_eye_corner_idxs: tuple[int, int] = (362, 263),
) -> tuple[float, float]:
    """
    Estimate gaze yaw and pitch from iris positions relative to eye corners.

    Positive yaw  → driver looking right.
    Positive pitch → driver looking up.

    Parameters
    ----------
    landmarks : np.ndarray
        Full 478-point MediaPipe normalised landmark array (N, 3).
    left_iris_idx, right_iris_idx : int
        MediaPipe iris centre landmark indices.
    left_eye_corner_idxs, right_eye_corner_idxs : tuple[int,int]
        (inner, outer) corner landmark indices for each eye.

    Returns
    -------
    gaze_yaw : float   (degrees estimate; approximate)
    gaze_pitch : float (degrees estimate; approximate)
    """
    # Left iris relative position within eye
    l_iris   = landmarks[left_iris_idx, :2]
    l_inner  = landmarks[left_eye_corner_idxs[0], :2]
    l_outer  = landmarks[left_eye_corner_idxs[1], :2]
    l_width  = np.linalg.norm(l_outer - l_inner) + 1e-9
    l_rel_x  = float((l_iris[0] - l_inner[0]) / l_width - 0.5)   # -0.5…+0.5

    # Right iris
    r_iris   = landmarks[right_iris_idx, :2]
    r_inner  = landmarks[right_eye_corner_idxs[0], :2]
    r_outer  = landmarks[right_eye_corner_idxs[1], :2]
    r_width  = np.linalg.norm(r_outer - r_inner) + 1e-9
    r_rel_x  = float((r_iris[0] - r_inner[0]) / r_width - 0.5)

    # Average horizontal gaze → yaw (scaled to degrees heuristically)
    gaze_yaw = (l_rel_x + r_rel_x) / 2.0 * 60.0

    # Vertical: use midpoint y relative to eye centre
    l_mid_y  = (l_inner[1] + l_outer[1]) / 2.0
    l_rel_y  = float(l_iris[1] - l_mid_y)
    r_mid_y  = (r_inner[1] + r_outer[1]) / 2.0
    r_rel_y  = float(r_iris[1] - r_mid_y)
    gaze_pitch = -((l_rel_y + r_rel_y) / 2.0) * 60.0

    return gaze_yaw, gaze_pitch


# ---------------------------------------------------------------------------
# Off-road gaze ratio tracker (stateful)
# ---------------------------------------------------------------------------

@dataclass
class OffRoadGazeTracker:
    """
    Tracks the fraction of recent frames where gaze is 'off road' (deviated
    beyond ``yaw_threshold`` or ``pitch_threshold`` degrees).

    Parameters
    ----------
    yaw_threshold : float
        |gaze_yaw| above this → driver not looking forward (degrees).
    pitch_threshold : float
        |gaze_pitch| below this (negative = looking down) → off-road (degrees).
    window_s : float
        Sliding window duration (seconds).
    fps : float
        Camera frame rate.
    """
    yaw_threshold:   float = 20.0
    pitch_threshold: float = -15.0
    window_s:        float = 10.0
    fps:             float = 30.0

    _flags: deque = field(
        default_factory=lambda: deque(maxlen=600), init=False, repr=False
    )

    def __post_init__(self) -> None:
        max_frames = int(self.window_s * self.fps) + 1
        self._flags = deque(maxlen=max_frames)

    def update(self, gaze_yaw: float, gaze_pitch: float) -> float:
        """
        Add one sample and return the current off-road gaze ratio in [0, 1].
        """
        off_road = abs(gaze_yaw) > self.yaw_threshold or gaze_pitch < self.pitch_threshold
        self._flags.append(1 if off_road else 0)
        n = len(self._flags)
        return float(sum(self._flags)) / n if n > 0 else 0.0

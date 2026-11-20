"""
features/ear.py
================
Eye Aspect Ratio (EAR) calculation, blink detection, and per-driver calibration.

References
----------
Soukupová & Čech (2016). "Real-Time Eye Blink Detection using Facial Landmarks."
Deng & Wu (2019). [14] in synopsis — DriCare tracker using EAR/MAR.

EAR formula
-----------
EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)

where p1..p6 are the six eye landmarks in order:
  p1 = left corner, p2 = upper-left, p3 = upper-right,
  p4 = right corner, p5 = lower-right, p6 = lower-left.

All functions here are **pure** (no side effects, no global state) so they
can be unit-tested with synthetic landmark arrays.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Core EAR function — pure, unit-testable
# ---------------------------------------------------------------------------

def compute_ear(eye_pts: np.ndarray) -> float:
    """
    Compute the Eye Aspect Ratio for one eye.

    Parameters
    ----------
    eye_pts : np.ndarray
        Shape (6, 2) or (6, 3) — six landmark [x, y(, z)] coordinates in the
        order expected by the EAR formula (see module docstring).
        Coordinates may be pixel-space or normalised (both produce the same ratio).

    Returns
    -------
    float
        EAR value in [0, ~0.5].  Values near 0 indicate a closed eye.
        Returns 0.0 if eye_pts is invalid (defensive).
    """
    if eye_pts.shape[0] != 6:
        return 0.0
    pts = eye_pts[:, :2].astype(np.float64)
    # Vertical distances
    A = np.linalg.norm(pts[1] - pts[5])   # p2 - p6
    B = np.linalg.norm(pts[2] - pts[4])   # p3 - p5
    # Horizontal distance
    C = np.linalg.norm(pts[0] - pts[3])   # p1 - p4
    if C < 1e-9:
        return 0.0
    return float((A + B) / (2.0 * C))


def extract_eye_points(landmarks: np.ndarray, indices: list[int]) -> np.ndarray:
    """
    Slice landmark array to get one eye's six points.

    Parameters
    ----------
    landmarks : np.ndarray
        Full landmark array shape (N, 3).
    indices : list[int]
        Six indices into the landmark array for the eye of interest.

    Returns
    -------
    np.ndarray  shape (6, 3)
    """
    return landmarks[indices, :]


# ---------------------------------------------------------------------------
# Blink detector (stateful, owns a per-instance deque)
# ---------------------------------------------------------------------------

@dataclass
class BlinkDetector:
    """
    Detects blinks from a stream of EAR values and tracks blink rate/duration.

    Parameters
    ----------
    ear_threshold_ratio : float
        EAR < (baseline_ear * ear_threshold_ratio) → eye considered closed.
        Loaded from config: ``behavioral.ear_drowsy_ratio`` (default 0.70).
    consec_frames_closed : int
        Minimum consecutive frames with low EAR before a blink is registered.
    fps : float
        Camera frame rate (used to convert frame counts to seconds).
    rate_window_s : float
        Sliding window (seconds) over which blink rate is computed.
    """
    ear_threshold_ratio:  float = 0.70
    consec_frames_closed: int   = 2
    fps:                  float = 30.0
    rate_window_s:        float = 60.0

    # Internal state
    _closed_frames:  int    = field(default=0, init=False, repr=False)
    _in_blink:       bool   = field(default=False, init=False, repr=False)
    _blink_start_ts: float  = field(default=0.0, init=False, repr=False)
    _blink_times:    deque  = field(default_factory=lambda: deque(maxlen=200),
                                   init=False, repr=False)
    _last_duration_ms: float = field(default=0.0, init=False, repr=False)
    baseline_ear:    float  = field(default=0.30, init=False, repr=False)

    def set_baseline(self, baseline: float) -> None:
        """Set per-driver calibrated baseline EAR."""
        self.baseline_ear = max(baseline, 0.10)

    @property
    def _threshold(self) -> float:
        return self.baseline_ear * self.ear_threshold_ratio

    def update(self, ear: float, ts_ms: float) -> tuple[bool, float, float]:
        """
        Feed one EAR sample and update blink state.

        Parameters
        ----------
        ear : float
            Current frame EAR (mean of both eyes, or one eye).
        ts_ms : float
            Current timestamp in epoch milliseconds.

        Returns
        -------
        blink_detected : bool
            True for the single frame when a blink ends (EAR rises above threshold).
        blink_rate_per_min : float
            Blink rate over the last ``rate_window_s`` seconds.
        last_blink_duration_ms : float
            Duration of the most recently completed blink (ms).
        """
        eye_closed = ear < self._threshold

        if eye_closed:
            if not self._in_blink:
                self._in_blink       = True
                self._blink_start_ts = ts_ms
            self._closed_frames += 1
            current_duration = ts_ms - self._blink_start_ts
            return False, self._compute_rate(ts_ms), max(self._last_duration_ms, current_duration)
        else:
            if self._in_blink and self._closed_frames >= self.consec_frames_closed:
                # Blink just ended
                duration_ms = ts_ms - self._blink_start_ts
                self._last_duration_ms = duration_ms
                self._blink_times.append(ts_ms)
                self._in_blink     = False
                self._closed_frames = 0
                return True, self._compute_rate(ts_ms), duration_ms
            self._in_blink      = False
            self._closed_frames = 0
            return False, self._compute_rate(ts_ms), self._last_duration_ms

    def _compute_rate(self, now_ms: float) -> float:
        window_start = now_ms - self.rate_window_s * 1000.0
        recent       = [t for t in self._blink_times if t >= window_start]
        return float(len(recent)) * (60_000.0 / (self.rate_window_s * 1000.0))


# ---------------------------------------------------------------------------
# PERCLOS tracker
# ---------------------------------------------------------------------------

class PERCLOSTracker:
    """
    Computes PERCLOS — the fraction of time the eyes are ≥ 80% closed —
    over a configurable sliding window (default 60 s).

    Per synopsis Section 4 step 2 and reference [8], [15]: PERCLOS is the
    primary leading indicator of micro-sleep onset.

    Parameters
    ----------
    window_s : float
        Sliding window duration in seconds.
    fps : float
        Camera frame rate.
    closed_threshold_pct : float
        Eye considered 'closed' when EAR < (baseline * closed_threshold_pct).
        0.80 corresponds to the 80 % closure criterion used in literature.
    """

    def __init__(
        self,
        window_s: float = 60.0,
        fps: float = 30.0,
        closed_threshold_pct: float = 0.80,
    ) -> None:
        max_frames          = int(window_s * fps) + 1
        self._window_s      = window_s
        self._fps           = fps
        self._threshold_pct = closed_threshold_pct
        self._timestamps:   deque = deque(maxlen=max_frames)
        self._closed_flags: deque = deque(maxlen=max_frames)
        self._baseline_ear: float = 0.30

    def set_baseline(self, baseline: float) -> None:
        self._baseline_ear = max(baseline, 0.10)

    def update(self, ear: float, ts_ms: float) -> float:
        """
        Feed one EAR sample and return the current PERCLOS.

        Returns
        -------
        float
            PERCLOS in [0, 1].  Values > 0.15 indicate mild drowsiness;
            > 0.30 moderate; > 0.50 critical (see config/thresholds.yaml).
        """
        threshold = self._baseline_ear * self._threshold_pct
        closed    = 1 if ear < threshold else 0

        # Prune samples outside the window
        window_start = ts_ms - self._window_s * 1000.0
        while self._timestamps and self._timestamps[0] < window_start:
            self._timestamps.popleft()
            self._closed_flags.popleft()

        self._timestamps.append(ts_ms)
        self._closed_flags.append(closed)

        n = len(self._closed_flags)
        return float(sum(self._closed_flags)) / n if n > 0 else 0.0


# ---------------------------------------------------------------------------
# Driver calibration
# ---------------------------------------------------------------------------

class EARCalibrator:
    """
    Collects EAR samples during the first ``calibration_s`` seconds of a session
    and reports the baseline (mean of stable open-eye samples).

    Usage
    -----
        cal = EARCalibrator(calibration_s=30.0)
        for frame in ...:
            if not cal.is_done:
                cal.add_sample(ear_mean)
        baseline = cal.baseline_ear
    """

    def __init__(self, calibration_s: float = 30.0, fps: float = 30.0) -> None:
        self._target_samples = int(calibration_s * fps)
        self._samples:    list[float] = []
        self._is_done:    bool        = False
        self._baseline:   float       = 0.30   # safe fallback

    @property
    def is_done(self) -> bool:
        return self._is_done

    @property
    def baseline_ear(self) -> float:
        return self._baseline

    def add_sample(self, ear: float) -> Optional[float]:
        """
        Add one EAR sample. Returns the baseline once calibration completes,
        or None while still collecting.
        """
        if self._is_done:
            return self._baseline
        if ear > 0.15:                       # discard clear blinks/outliers
            self._samples.append(ear)
        if len(self._samples) >= self._target_samples:
            arr = np.array(self._samples)
            # Use the 50th–90th percentile to exclude blinks/head turns
            self._baseline = float(np.percentile(arr, 70))
            self._is_done  = True
            return self._baseline
        return None

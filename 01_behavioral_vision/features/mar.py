"""
features/mar.py
================
Mouth Aspect Ratio (MAR) and yawn detection.

MAR formula (analogous to EAR):
  MAR = (||A||+||B||+||C||) / (3 * ||D||)

where A,B,C are vertical mouth distances and D is the horizontal span.

Yawn criteria (config-driven — all thresholds in config/thresholds.yaml):
  - MAR > (baseline_mar * 1.5) for ≥ ``yawn_duration_min_s`` seconds → yawn event
  - Yawn count tracked over a rolling window (default 60 s, Tier 1 frequency rule)
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Core MAR function — pure
# ---------------------------------------------------------------------------

def compute_mar(mouth_pts: np.ndarray) -> float:
    """
    Compute Mouth Aspect Ratio.

    Parameters
    ----------
    mouth_pts : np.ndarray
        Shape (6, 2) or (6, 3). The six landmark points should be:
          [0] left corner, [1] right corner,
          [2] upper-inner-top, [3] lower-inner-bottom,
          [4] upper-outer-top, [5] lower-outer-bottom.
        The exact MediaPipe indices are: [61, 291, 13, 14, 17, 0]
        (see landmarks/detector.py MOUTH_IDX).

    Returns
    -------
    float
        MAR in [0, ~1.5]; values > 0.6 typically indicate an open mouth/yawn.
    """
    if mouth_pts.shape[0] != 6:
        return 0.0
    pts = mouth_pts[:, :2].astype(np.float64)
    # Vertical distances (3 pairs)
    A = np.linalg.norm(pts[2] - pts[5])   # upper-outer ↔ lower-outer
    B = np.linalg.norm(pts[3] - pts[4])   # upper-inner ↔ lower-outer (cross)
    C = np.linalg.norm(pts[2] - pts[3])   # inner pair
    # Horizontal distance
    D = np.linalg.norm(pts[0] - pts[1])
    if D < 1e-9:
        return 0.0
    return float((A + B + C) / (3.0 * D))


# ---------------------------------------------------------------------------
# Yawn detector (stateful)
# ---------------------------------------------------------------------------

@dataclass
class YawnDetector:
    """
    Detects individual yawn events from a MAR time series.

    Parameters
    ----------
    mar_open_ratio : float
        MAR must exceed (baseline_mar * mar_open_ratio) to trigger a yawn.
    yawn_duration_min_s : float
        Minimum duration (seconds) of sustained high MAR to count as a yawn.
    count_window_min : float
        Sliding window (minutes) for the yawn count.
    fps : float
        Camera frame rate, used to convert frame duration to seconds.
    """
    mar_open_ratio:     float = 1.5
    yawn_duration_min_s: float = 1.0
    count_window_min:   float = 1.0
    count_window_s:     Optional[float] = None
    fps:                float = 30.0

    baseline_mar: float = field(default=0.35, init=False, repr=False)
    _open_start:  Optional[float] = field(default=None, init=False, repr=False)
    _yawn_active: bool            = field(default=False, init=False, repr=False)
    _yawn_times:  deque           = field(
        default_factory=lambda: deque(maxlen=100), init=False, repr=False
    )

    def set_baseline(self, baseline_mar: float) -> None:
        self.baseline_mar = max(baseline_mar, 0.10)

    @property
    def _open_threshold(self) -> float:
        return self.baseline_mar * self.mar_open_ratio

    def update(self, mar: float, ts_ms: float) -> tuple[bool, int]:
        """
        Feed one MAR sample.

        Returns
        -------
        yawn_active : bool
            True while the driver's mouth is open in a yawn.
        yawn_count_5min : int
            Number of completed yawns in the rolling count window
            (contract field name retained; window is ``count_window_s``).
        """
        is_open = mar > self._open_threshold

        if is_open:
            if self._open_start is None:
                self._open_start  = ts_ms
                self._yawn_active = False
            else:
                elapsed_s = (ts_ms - self._open_start) / 1000.0
                if elapsed_s >= self.yawn_duration_min_s:
                    self._yawn_active = True
        else:
            if self._yawn_active and self._open_start is not None:
                self._yawn_times.append(ts_ms)   # record completed yawn
            self._open_start  = None
            self._yawn_active = False

        return self._yawn_active, self._count_recent(ts_ms)

    def _window_ms(self) -> float:
        if self.count_window_s is not None:
            return float(self.count_window_s) * 1000.0
        return float(self.count_window_min) * 60_000.0

    def _count_recent(self, now_ms: float) -> int:
        window_start = now_ms - self._window_ms()
        return sum(1 for t in self._yawn_times if t >= window_start)

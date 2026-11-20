"""
tests/test_features.py
=======================
Unit tests for all feature extraction functions.
These tests use only synthetic landmark arrays — no camera, no MediaPipe.

Run with:  pytest 01_behavioral_vision/tests/ -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# Make the package importable from repo root
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "01_behavioral_vision"))

from features.ear import (
    EARCalibrator,
    BlinkDetector,
    PERCLOSTracker,
    compute_ear,
    extract_eye_points,
)
from features.mar import YawnDetector, compute_mar
from features.gaze import OffRoadGazeTracker, compute_gaze
from features.head_pose import NodDetector


# ─────────────────────────────────────────────
# Helpers — synthetic landmark arrays
# ─────────────────────────────────────────────

def _make_open_eye_pts(ear: float = 0.30) -> np.ndarray:
    """
    Build a synthetic 6-point eye landmark array yielding the given EAR.
    p1=(0,0), p4=(1,0) → horizontal distance = 1.
    Vertical A = B = ear (so EAR = 2*ear / (2*1) = ear).
    """
    h = ear / 2.0
    pts = np.array([
        [0.0, 0.0,  0.0],   # p1 left corner
        [0.25, h, 0.0],     # p2 upper-left
        [0.75, h, 0.0],     # p3 upper-right
        [1.0, 0.0,  0.0],   # p4 right corner
        [0.75, -h, 0.0],    # p5 lower-right
        [0.25, -h, 0.0],    # p6 lower-left
    ], dtype=np.float32)
    return pts


def _make_closed_eye_pts() -> np.ndarray:
    return _make_open_eye_pts(ear=0.01)


def _make_open_mouth_pts(mar: float = 0.55) -> np.ndarray:
    """6-point mouth array yielding an approximate MAR ≈ mar."""
    return np.array([
        [0.0, 0.0,  0.0],      # left corner
        [1.0, 0.0,  0.0],      # right corner
        [0.5, mar,  0.0],      # upper inner
        [0.5, -mar, 0.0],      # lower inner
        [0.5, mar,  0.0],      # upper outer (duplicate)
        [0.5, -mar, 0.0],      # lower outer
    ], dtype=np.float32)


# ─────────────────────────────────────────────
# EAR tests
# ─────────────────────────────────────────────

class TestComputeEAR:
    def test_open_eye_value(self):
        pts = _make_open_eye_pts(ear=0.30)
        result = compute_ear(pts)
        assert abs(result - 0.30) < 0.01, f"EAR={result} expected ~0.30"

    def test_closed_eye_near_zero(self):
        pts = _make_closed_eye_pts()
        result = compute_ear(pts)
        assert result < 0.05, f"Closed eye EAR={result} should be near 0"

    def test_wrong_shape_returns_zero(self):
        pts = np.zeros((4, 2))  # wrong shape
        assert compute_ear(pts) == 0.0

    def test_degenerate_horizontal_returns_zero(self):
        pts = np.zeros((6, 2))  # all points at origin → C=0
        assert compute_ear(pts) == 0.0

    def test_ear_range(self):
        for ear_val in [0.05, 0.15, 0.25, 0.35]:
            pts = _make_open_eye_pts(ear=ear_val)
            result = compute_ear(pts)
            assert 0.0 <= result <= 1.0


# ─────────────────────────────────────────────
# PERCLOS tests
# ─────────────────────────────────────────────

class TestPERCLOSTracker:
    def test_all_open_eyes_perclos_zero(self):
        tracker = PERCLOSTracker(window_s=5.0, fps=10.0)
        tracker.set_baseline(0.30)
        ts = 1000.0
        for _ in range(50):
            result = tracker.update(0.30, ts)
            ts += 100.0
        assert result < 0.05, f"PERCLOS={result} should be near 0 for open eyes"

    def test_all_closed_eyes_perclos_high(self):
        tracker = PERCLOSTracker(window_s=5.0, fps=10.0)
        tracker.set_baseline(0.30)
        ts = 1000.0
        for _ in range(50):
            result = tracker.update(0.02, ts)  # eyes closed
            ts += 100.0
        assert result > 0.90, f"PERCLOS={result} should be near 1.0 for closed eyes"

    def test_perclos_in_range(self):
        tracker = PERCLOSTracker(window_s=5.0, fps=10.0)
        tracker.set_baseline(0.30)
        ts = 1000.0
        for i in range(50):
            ear = 0.02 if i % 2 == 0 else 0.30
            result = tracker.update(ear, ts)
            ts += 100.0
        assert 0.0 <= result <= 1.0

    def test_window_sliding(self):
        """Old samples outside the window should not count."""
        tracker = PERCLOSTracker(window_s=2.0, fps=10.0)
        tracker.set_baseline(0.30)
        ts = 0.0
        # 2 seconds of closed eyes
        for _ in range(20):
            tracker.update(0.02, ts)
            ts += 100.0
        # 3 seconds of open eyes — window should now be clean
        for _ in range(30):
            result = tracker.update(0.30, ts)
            ts += 100.0
        assert result < 0.05, f"PERCLOS={result} after eyes open should be near 0"


# ─────────────────────────────────────────────
# Blink detector tests
# ─────────────────────────────────────────────

class TestBlinkDetector:
    def test_no_blink_while_open(self):
        det = BlinkDetector(fps=10.0)
        det.set_baseline(0.30)
        ts = 1000.0
        for _ in range(20):
            blink, _, _ = det.update(0.30, ts)
            ts += 100.0
            assert not blink

    def test_blink_detected_after_closure(self):
        det = BlinkDetector(fps=10.0, consec_frames_closed=2)
        det.set_baseline(0.30)
        ts = 1000.0
        # Open
        det.update(0.30, ts); ts += 100.0
        # Closed for 3 frames
        det.update(0.05, ts); ts += 100.0
        det.update(0.05, ts); ts += 100.0
        det.update(0.05, ts); ts += 100.0
        # Open → should detect blink
        blink, rate, dur = det.update(0.30, ts)
        assert blink, "Blink should be detected after eye opens"
        assert dur > 0, f"Blink duration={dur} should be > 0"

    def test_blink_rate_non_negative(self):
        det = BlinkDetector(fps=10.0)
        det.set_baseline(0.30)
        ts = 1000.0
        for _ in range(30):
            _, rate, _ = det.update(0.30, ts)
            ts += 100.0
            assert rate >= 0.0


# ─────────────────────────────────────────────
# MAR / Yawn tests
# ─────────────────────────────────────────────

class TestComputeMAR:
    def test_open_mouth_high_mar(self):
        pts = _make_open_mouth_pts(mar=0.55)
        result = compute_mar(pts)
        assert result > 0.3, f"MAR={result} for open mouth should be > 0.3"

    def test_closed_mouth_low_mar(self):
        pts = _make_open_mouth_pts(mar=0.01)
        result = compute_mar(pts)
        assert result < 0.15, f"MAR={result} for closed mouth should be < 0.15"

    def test_wrong_shape_returns_zero(self):
        pts = np.zeros((4, 2))
        assert compute_mar(pts) == 0.0


class TestYawnDetector:
    def test_no_yawn_for_closed_mouth(self):
        det = YawnDetector(yawn_duration_min_s=1.0, fps=10.0)
        det.set_baseline(0.35)
        ts = 1000.0
        for _ in range(20):
            active, count = det.update(0.10, ts)
            ts += 100.0
        assert not active

    def test_yawn_detected_after_duration(self):
        det = YawnDetector(yawn_duration_min_s=1.0, fps=10.0)
        det.set_baseline(0.35)
        ts = 0.0
        # Open mouth for 2 seconds = 20 frames @ 10fps
        active = False
        for _ in range(20):
            active, _ = det.update(0.80, ts)
            ts += 100.0
        assert active, "Yawn should be active after sustained open mouth"


# ─────────────────────────────────────────────
# Gaze tests
# ─────────────────────────────────────────────

class TestOffRoadGazeTracker:
    def test_forward_gaze_zero_ratio(self):
        tracker = OffRoadGazeTracker(yaw_threshold=20.0)
        for _ in range(50):
            ratio = tracker.update(0.0, 0.0)  # looking straight ahead
        assert ratio < 0.01

    def test_off_road_gaze_high_ratio(self):
        tracker = OffRoadGazeTracker(yaw_threshold=20.0)
        for _ in range(50):
            ratio = tracker.update(45.0, 0.0)  # looking far right
        assert ratio > 0.95


# ─────────────────────────────────────────────
# Head pose / nod tests
# ─────────────────────────────────────────────

class TestNodDetector:
    def test_no_nod_for_stable_pitch(self):
        det = NodDetector(nod_threshold_deg=15.0)
        for _ in range(10):
            result = det.update(0.0)
        assert not result

    def test_nod_detected_on_rapid_pitch_change(self):
        det = NodDetector(nod_threshold_deg=15.0, nod_window_frames=5)
        pitches = [0.0, 5.0, 15.0, 25.0, 35.0]  # rapid droop
        result = False
        for p in pitches:
            result = det.update(p)
        assert result, "Nod should be detected for large pitch change"

    def test_no_nod_for_gradual_change(self):
        det = NodDetector(nod_threshold_deg=15.0, nod_window_frames=5)
        result = False
        for i in range(10):
            result = det.update(float(i) * 0.5)  # 0 → 4.5 deg over 10 frames
        assert not result, "Gradual pitch change should not trigger nod"


# ─────────────────────────────────────────────
# EAR Calibrator tests
# ─────────────────────────────────────────────

class TestEARCalibrator:
    def test_calibration_completes(self):
        cal = EARCalibrator(calibration_s=2.0, fps=10.0)
        baseline = None
        for _ in range(25):
            baseline = cal.add_sample(0.30)
        assert cal.is_done
        assert baseline is not None
        assert 0.10 < baseline < 0.50

    def test_baseline_ignores_blinks(self):
        cal = EARCalibrator(calibration_s=2.0, fps=10.0)
        # Feed mostly open-eye values but with occasional blinks
        for i in range(25):
            ear = 0.01 if i % 5 == 0 else 0.30
            cal.add_sample(ear)
        # Baseline should still be near 0.30, not pulled down by blinks
        assert cal.baseline_ear > 0.20, f"Baseline={cal.baseline_ear} pulled too low by blinks"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

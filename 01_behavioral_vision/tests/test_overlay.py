"""
tests/test_overlay.py
=====================
Unit tests for real-time visual overlay rendering.
"""

import numpy as np
import pytest

from landmarks.detector import LandmarkResult
from visualization.overlay import draw_drowsiness_overlay


def test_overlay_runs_without_face():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    features = {
        "face_detected": False,
        "ear_mean": 0.0,
        "mar": 0.0,
        "behavior_score": 0.0,
        "perclos_60s": 0.0,
        "yawn_count_5min": 0,
    }
    out = draw_drowsiness_overlay(frame, features, landmark_res=None)
    assert out.shape == (480, 640, 3)
    assert out.dtype == np.uint8


def test_overlay_runs_with_face_open_eyes():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # 478 mock landmarks
    landmarks = np.random.uniform(0.3, 0.7, size=(478, 3)).astype(np.float32)
    landmark_res = LandmarkResult(
        face_detected=True,
        quality=1.0,
        landmarks=landmarks,
        image_wh=(640, 480),
    )
    features = {
        "face_detected": True,
        "ear_mean": 0.35,
        "mar": 0.10,
        "behavior_score": 0.05,
        "perclos_60s": 0.02,
        "yawn_count_5min": 0,
    }
    out = draw_drowsiness_overlay(frame, features, landmark_res=landmark_res)
    assert out.shape == (480, 640, 3)


def test_overlay_runs_with_closed_eyes_and_alert():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    landmarks = np.random.uniform(0.3, 0.7, size=(478, 3)).astype(np.float32)
    landmark_res = LandmarkResult(
        face_detected=True,
        quality=1.0,
        landmarks=landmarks,
        image_wh=(640, 480),
    )
    features = {
        "face_detected": True,
        "ear_mean": 0.15,
        "mar": 0.65,
        "behavior_score": 0.85,
        "perclos_60s": 0.45,
        "yawn_count_5min": 3,
        "yawn_active": True,
    }
    out = draw_drowsiness_overlay(frame, features, landmark_res=landmark_res)
    assert out.shape == (480, 640, 3)


def test_overlay_runs_with_68_points():
    frame = np.zeros((480, 640), dtype=np.uint8)  # Grayscale
    landmarks = np.random.uniform(0.3, 0.7, size=(68, 2)).astype(np.float32)
    landmark_res = LandmarkResult(
        face_detected=True,
        quality=1.0,
        landmarks=landmarks,
        image_wh=(640, 480),
    )
    features = {
        "face_detected": True,
        "ear_mean": 0.28,
        "mar": 0.12,
        "behavior_score": 0.10,
        "perclos_60s": 0.0,
        "yawn_count_5min": 0,
    }
    out = draw_drowsiness_overlay(frame, features, landmark_res=landmark_res)
    assert out.shape == (480, 640, 3)  # Converted to 3-channel BGR

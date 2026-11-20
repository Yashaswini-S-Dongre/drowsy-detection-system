"""
features/landmark_detector.py
==============================
Compatibility alias for the original specification filename.

The canonical implementation lives in ``landmarks.detector``.
This module re-exports everything from there so that code importing
from ``features.landmark_detector`` (as the original spec required) works
identically to importing from ``landmarks.detector``.
"""

from landmarks.detector import *
from landmarks.detector import (  # noqa: F401
    DlibLandmarkDetector,
    LandmarkResult,
    MediaPipeLandmarkDetector,
    MockLandmarkDetector,
    build_detector,
)

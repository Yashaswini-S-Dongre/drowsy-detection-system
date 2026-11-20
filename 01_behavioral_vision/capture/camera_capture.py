"""
capture/camera_capture.py
==========================
Compatibility alias for the original specification filename.

The canonical implementation lives in ``capture.frame_source``.
This module re-exports everything from there so that code importing
from ``capture.camera_capture`` (as the original spec required) works
identically to importing from ``capture.frame_source``.
"""

from capture.frame_source import *
from capture.frame_source import FrameMeta, FrameSource, SourceMode  # noqa: F401

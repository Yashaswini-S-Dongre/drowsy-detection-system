"""
capture/frame_source.py
========================
Hardware-abstracted frame source for the behavioural vision pipeline.

Supports three source modes (set via config.yaml `behavioral.source`):
  - ``webcam``    : live laptop/USB webcam (index 0 by default)
  - ``video``     : MP4 / AVI file replay at native FPS
  - ``synthetic`` : procedurally generated frames for CI / demo / unit tests

Privacy guarantee
-----------------
Frames are held only in a fixed-size in-memory ring buffer.
``write_raw_video`` must be ``False`` (enforced by the privacy guard in
03_fusion_edge_platform/privacy/guard.py).  This module never writes frames
to disk or network — it only yields numpy arrays to the caller.

Usage
-----
    from capture.frame_source import FrameSource, SourceMode
    src = FrameSource(mode=SourceMode.WEBCAM, ring_buffer_size=300)
    for frame in src:
        process(frame)
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Generator, Optional

import cv2
import numpy as np


class SourceMode(str, Enum):
    WEBCAM    = "webcam"
    VIDEO     = "video"
    SYNTHETIC = "synthetic"


@dataclass
class FrameMeta:
    """Lightweight metadata attached to every captured frame."""
    frame_id:   int
    capture_ts: float          # epoch ms at capture time
    source:     SourceMode
    width:      int
    height:     int


class FrameSource:
    """
    Hardware-abstracted camera source with IR-emulation preprocessing and
    a fixed-size privacy ring buffer.

    Parameters
    ----------
    mode : SourceMode
        Source backend to use.
    video_path : str
        Path to video file (only used when ``mode=VIDEO``).
    camera_index : int
        OS camera index (only used when ``mode=WEBCAM``).
    ring_buffer_size : int
        Number of frames retained in RAM before oldest frame is overwritten.
        This is the privacy guarantee — raw frames are never persisted beyond
        this sliding window.
    ir_emulation : bool
        When True, applies grayscale + CLAHE + gamma correction to emulate
        an IR camera.  This improves robustness in low-light conditions.
    target_fps : float
        Requested frame rate.  Source will throttle or duplicate frames to
        approach this rate.
    """

    def __init__(
        self,
        mode: SourceMode = SourceMode.WEBCAM,
        video_path: str = "",
        camera_index: int = 0,
        ring_buffer_size: int = 300,
        ir_emulation: bool = True,
        target_fps: float = 30.0,
    ) -> None:
        self.mode             = mode
        self.video_path       = video_path
        self.camera_index     = camera_index
        self.ring_buffer_size = ring_buffer_size
        self.ir_emulation     = ir_emulation
        self.target_fps       = target_fps

        self._cap:         Optional[cv2.VideoCapture] = None
        self._ring_buffer: deque[np.ndarray] = deque(maxlen=ring_buffer_size)
        self._frame_id:    int = 0
        self._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Initialise the capture backend."""
        if self.mode == SourceMode.WEBCAM:
            self._cap = cv2.VideoCapture(self.camera_index)
            if not self._cap.isOpened():
                raise RuntimeError(
                    f"Cannot open webcam index {self.camera_index}. "
                    "Try --source synthetic for testing without a camera."
                )
        elif self.mode == SourceMode.VIDEO:
            self._cap = cv2.VideoCapture(self.video_path)
            if not self._cap.isOpened():
                raise RuntimeError(f"Cannot open video file: {self.video_path}")
        # SYNTHETIC mode needs no backend

    def release(self) -> None:
        """Release underlying capture resources."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        # Explicitly clear ring buffer (privacy: zero RAM references)
        self._ring_buffer.clear()

    def read_frame(self) -> tuple[bool, Optional[np.ndarray], FrameMeta]:
        """
        Read one frame from the source.

        Returns
        -------
        ok : bool
            False if the source is exhausted or errored.
        frame : np.ndarray or None
            BGR or grayscale frame (after IR emulation preprocessing).
        meta : FrameMeta
            Metadata for this frame.
        """
        ts = time.time() * 1000.0

        if self.mode == SourceMode.SYNTHETIC:
            frame, ok = self._generate_synthetic_frame(), True
        else:
            ok, raw = self._cap.read()  # type: ignore[union-attr]
            frame = raw if ok else None

        if not ok or frame is None:
            meta = FrameMeta(self._frame_id, ts, self.mode, 0, 0)
            return False, None, meta

        if self.ir_emulation:
            frame = self._apply_ir_emulation(frame)

        # Store in ring buffer (oldest frame silently overwritten)
        self._ring_buffer.append(frame)

        h, w = frame.shape[:2]
        meta = FrameMeta(self._frame_id, ts, self.mode, w, h)
        self._frame_id += 1
        return True, frame, meta

    def __iter__(self) -> Generator[tuple[np.ndarray, FrameMeta], None, None]:
        """Iterate frames; automatically manages frame rate."""
        interval = 1.0 / max(self.target_fps, 1.0)
        while True:
            t0    = time.time()
            ok, frame, meta = self.read_frame()
            if not ok:
                break
            yield frame, meta  # type: ignore[misc]
            elapsed = time.time() - t0
            if elapsed < interval:
                time.sleep(interval - elapsed)

    def __enter__(self) -> "FrameSource":
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_ir_emulation(self, frame: np.ndarray) -> np.ndarray:
        """
        IR-camera emulation pipeline:
          1. Convert to grayscale
          2. CLAHE (Contrast Limited Adaptive Histogram Equalisation)
          3. Gamma correction (γ = 1.5) to boost dark regions
        Returns a single-channel uint8 array.
        """
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame.copy()

        # CLAHE
        clahe_out = self._clahe.apply(gray)

        # Gamma correction: output = 255 * (input/255)^(1/gamma)
        gamma     = 1.5
        inv_gamma = 1.0 / gamma
        lut = np.array([
            int(((i / 255.0) ** inv_gamma) * 255)
            for i in range(256)
        ], dtype=np.uint8)
        return cv2.LUT(clahe_out, lut)

    def _generate_synthetic_frame(self) -> np.ndarray:
        """
        Generate a synthetic 480×640 grayscale frame with a simple oval
        approximating a face ellipse — sufficient for unit tests and CI
        without a real camera.  Labelled SYNTHETIC in frame_id.
        """
        h, w = 480, 640
        frame = np.zeros((h, w), dtype=np.uint8)
        # Face oval
        cx, cy = w // 2, h // 2
        cv2.ellipse(frame, (cx, cy), (120, 160), 0, 0, 360, 180, -1)
        # Eye outlines
        cv2.ellipse(frame, (cx - 45, cy - 40), (22, 12), 0, 0, 360, 40, -1)
        cv2.ellipse(frame, (cx + 45, cy - 40), (22, 12), 0, 0, 360, 40, -1)
        # Pupil dots
        cv2.circle(frame, (cx - 45, cy - 40), 6, 20, -1)
        cv2.circle(frame, (cx + 45, cy - 40), 6, 20, -1)
        # Mouth
        cv2.ellipse(frame, (cx, cy + 55), (35, 15), 0, 0, 180, 60, 2)
        # Add frame counter as subtle noise
        noise = np.random.randint(0, 8, frame.shape, dtype=np.uint8)
        frame = cv2.add(frame, noise)
        return frame

    @property
    def ring_buffer_count(self) -> int:
        """Number of frames currently held in the ring buffer."""
        return len(self._ring_buffer)

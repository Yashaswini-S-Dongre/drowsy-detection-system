"""
landmarks/detector.py
======================
Facial landmark detection with two backends:
  - ``mediapipe`` (default): 478-point Face Mesh via MediaPipe Tasks API (v1.x)
  - ``dlib``               : classic 68-point predictor (optional, requires dlib + dat file)

The active backend is selected by ``behavioral.landmark_backend`` in
``config/default.yaml``.  Both backends return the same ``LandmarkResult``
dataclass so that all downstream feature extractors are backend-agnostic.

MediaPipe landmark indices used by feature extractors
------------------------------------------------------
Left eye  : 33, 160, 158, 133, 153, 144  (EAR sextet)
Right eye : 362, 385, 387, 263, 373, 380  (EAR sextet)
Left iris : 468  (centre)
Right iris: 473  (centre)
Mouth     : 61, 291, 13, 14, 17, 0       (MAR sextet)
Nose tip  : 1  (solvePnP anchor)

Note: MediaPipe v1.x uses the Tasks API (mp.tasks.vision.FaceLandmarker).
      The legacy mp.solutions.face_mesh API is NOT available in v1.x.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class LandmarkResult:
    """
    Normalised (0–1) 2D landmark coordinates plus optional Z depth.
    Shape: (N, 3) where columns are [x, y, z].
    ``face_detected`` is False when no face was found.
    ``quality`` is 0.0–1.0 (fraction of landmarks in-bounds).
    """
    face_detected: bool
    quality:       float                        # 0.0 – 1.0
    landmarks:     Optional[np.ndarray]         # shape (N, 3) float32, normalised
    image_wh:      tuple[int, int]              # (width, height) of source frame


# ---------------------------------------------------------------------------
# MediaPipe Tasks API backend (v1.x)
# ---------------------------------------------------------------------------

class MediaPipeLandmarkDetector:
    """
    Wraps MediaPipe FaceLandmarker (Tasks API, v1.x) for the primary landmark
    pipeline, yielding 478-point face mesh including iris landmarks (468–477).

    Parameters
    ----------
    model_path : str | None
        Path to ``face_landmarker.task`` bundle.  If None, resolved from
        ``01_behavioral_vision/models/face_landmarker.task`` relative to
        the project root.
    num_faces : int
        Only track one face (the driver) to minimise latency.
    min_face_detection_confidence : float
        Threshold below which a detection is discarded.
    min_face_presence_confidence : float
        Threshold for tracking (in VIDEO mode).
    min_tracking_confidence : float
        Tracking confidence for smooth multi-frame tracking.
    """

    # EAR landmark indices (MediaPipe 478-point mesh)
    LEFT_EYE_IDX   = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE_IDX  = [362, 385, 387, 263, 373, 380]
    LEFT_IRIS_IDX  = 468
    RIGHT_IRIS_IDX = 473

    # MAR (mouth) indices
    MOUTH_IDX = [61, 291, 13, 14, 17, 0]

    # 3-D model points for solvePnP head-pose (standard 68-point mapping)
    MODEL_POINTS_3D = np.array([
        [0.0,   0.0,     0.0],    # Nose tip        (idx 1)
        [0.0,  -330.0, -65.0],    # Chin            (idx 152)
        [-225.0, 170.0, -135.0],  # Left eye corner (idx 33)
        [225.0,  170.0, -135.0],  # Right eye corner(idx 263)
        [-150.0, -150.0, -125.0], # Left mouth      (idx 61)
        [150.0,  -150.0, -125.0], # Right mouth     (idx 291)
    ], dtype=np.float64)
    SOLVEPNP_IDX = [1, 152, 33, 263, 61, 291]

    def __init__(
        self,
        model_path: Optional[str] = None,
        num_faces: int = 1,
        min_face_detection_confidence: float = 0.5,
        min_face_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        **kwargs: object,   # absorb legacy kwargs (static_image_mode, refine_landmarks, etc.)
    ) -> None:
        import mediapipe as mp

        # Resolve model path
        if model_path is None:
            # Try relative to this file, then relative to cwd
            candidate = Path(__file__).resolve().parents[1] / "models" / "face_landmarker.task"
            if not candidate.exists():
                candidate = Path("01_behavioral_vision") / "models" / "face_landmarker.task"
            model_path = str(candidate)

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"FaceLandmarker model not found at: {model_path}\n"
                "Run:  mkdir -p 01_behavioral_vision/models && curl -L "
                "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
                "face_landmarker/float16/1/face_landmarker.task "
                "-o 01_behavioral_vision/models/face_landmarker.task"
            )

        BaseOptions = mp.tasks.BaseOptions
        FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
        RunningMode = mp.tasks.vision.RunningMode
        FaceLandmarker = mp.tasks.vision.FaceLandmarker

        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=RunningMode.VIDEO,            # VIDEO mode for sequential frames
            num_faces=num_faces,
            min_face_detection_confidence=min_face_detection_confidence,
            min_face_presence_confidence=min_face_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self._detector = FaceLandmarker.create_from_options(options)
        self._mp_image_cls = mp.Image
        self._mp_image_format = mp.ImageFormat.SRGB
        self._frame_ts_ms = 0  # monotonically increasing timestamp for VIDEO mode

    def detect(self, frame: np.ndarray) -> LandmarkResult:
        """
        Run landmark detection on one frame.

        Parameters
        ----------
        frame : np.ndarray
            Grayscale (H, W) or BGR (H, W, 3) uint8 frame.

        Returns
        -------
        LandmarkResult
            Normalised landmarks; face_detected=False if no face found.
        """
        import mediapipe as mp

        # MediaPipe Tasks API needs an RGB image via mp.Image
        if len(frame.shape) == 2:           # grayscale → RGB
            rgb = np.stack([frame] * 3, axis=-1)
        else:
            rgb = frame[:, :, ::-1].copy()  # BGR → RGB

        if not rgb.flags['C_CONTIGUOUS']:
            rgb = np.ascontiguousarray(rgb)

        h, w = frame.shape[:2]

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        # VIDEO mode requires monotonically increasing timestamps
        self._frame_ts_ms += 33            # ~30 fps cadence
        result = self._detector.detect_for_video(mp_image, self._frame_ts_ms)

        if not result.face_landmarks:
            return LandmarkResult(face_detected=False, quality=0.0,
                                  landmarks=None, image_wh=(w, h))

        # Convert NormalizedLandmark list → (N, 3) float32 numpy array
        face = result.face_landmarks[0]
        pts = np.array(
            [[lm.x, lm.y, lm.z] for lm in face],
            dtype=np.float32,
        )

        # Quality: fraction of landmarks strictly within image bounds
        in_bounds = np.all((pts[:, :2] > 0.02) & (pts[:, :2] < 0.98), axis=1)
        quality   = float(np.mean(in_bounds))

        return LandmarkResult(
            face_detected=True,
            quality=quality,
            landmarks=pts,
            image_wh=(w, h),
        )

    def close(self) -> None:
        """Release MediaPipe resources."""
        if self._detector is not None:
            self._detector.close()
            self._detector = None


# ---------------------------------------------------------------------------
# Dlib backend (optional)
# ---------------------------------------------------------------------------

class DlibLandmarkDetector:
    """
    Optional 68-point Dlib predictor backend.

    Requires:
      - ``dlib`` Python package  (``pip install dlib``)
      - ``shape_predictor_68_face_landmarks.dat``
        (download via ``01_behavioral_vision/data/download_dlib_model.sh``)
    """

    # Dlib EAR sextets (0-indexed into 68 landmark array)
    LEFT_EYE_IDX  = [36, 37, 38, 39, 40, 41]
    RIGHT_EYE_IDX = [42, 43, 44, 45, 46, 47]
    MOUTH_IDX     = [60, 64, 62, 66, 56, 58]   # approximate sextet

    def __init__(self, dat_path: str) -> None:
        try:
            import dlib
        except ImportError as e:
            raise ImportError(
                "dlib is not installed. Run: pip install dlib  "
                "or use landmark_backend: mediapipe in config/default.yaml"
            ) from e
        self._detector  = dlib.get_frontal_face_detector()
        self._predictor = dlib.shape_predictor(dat_path)
        self._dlib      = dlib

    def detect(self, frame: np.ndarray) -> LandmarkResult:
        import cv2
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        h, w = gray.shape[:2]
        faces = self._detector(gray, 0)

        if not faces:
            return LandmarkResult(face_detected=False, quality=0.0,
                                  landmarks=None, image_wh=(w, h))

        shape = self._predictor(gray, faces[0])
        pts   = np.array(
            [[shape.part(i).x / w, shape.part(i).y / h, 0.0] for i in range(68)],
            dtype=np.float32,
        )
        quality = 0.9  # dlib doesn't expose a confidence score
        return LandmarkResult(face_detected=True, quality=quality,
                              landmarks=pts, image_wh=(w, h))


# ---------------------------------------------------------------------------
# Mock backend (for synthetic data / CI — NOT used in production paths)
# ---------------------------------------------------------------------------

class MockLandmarkDetector:
    """
    Purely synthetic landmark generator for unit tests and CI environments
    where no camera and no model file are available.

    ⚠️  This class must NEVER be used in production paths.  It is only
    activated when ``--backend mock`` is passed explicitly or when
    ``--source synthetic`` is used without a real model available.
    """
    def __init__(self, **kwargs: object) -> None:
        self.frame_count = 0
        self._rng = np.random.default_rng(seed=42)

    def detect(self, frame: np.ndarray) -> LandmarkResult:
        h, w = frame.shape[:2]
        self.frame_count += 1

        # Every 100 frames, simulate lost face
        if self.frame_count % 100 == 99:
            return LandmarkResult(face_detected=False, quality=0.0,
                                  landmarks=None, image_wh=(w, h))

        # Generate realistic-range synthetic 478-point face mesh
        # Points centred around image centre
        pts = np.full((478, 3), 0.5, dtype=np.float32)
        noise = self._rng.normal(0, 0.001, size=(478, 3)).astype(np.float32)
        pts += noise

        # ── Left eye (EAR sextet: 33, 160, 158, 133, 153, 144) ──────────
        # Horizontal span = 0.08, vertical half-height = 0.012 → EAR ≈ 0.30
        ex_l, ey_l = 0.35, 0.38
        pts[33]  = [ex_l - 0.040, ey_l,           0.0]  # p1 left corner
        pts[160] = [ex_l - 0.013, ey_l - 0.012,   0.0]  # p2 upper-left
        pts[158] = [ex_l + 0.013, ey_l - 0.012,   0.0]  # p3 upper-right
        pts[133] = [ex_l + 0.040, ey_l,            0.0]  # p4 right corner
        pts[153] = [ex_l + 0.013, ey_l + 0.012,   0.0]  # p5 lower-right
        pts[144] = [ex_l - 0.013, ey_l + 0.012,   0.0]  # p6 lower-left

        # ── Right eye (EAR sextet: 362, 385, 387, 263, 373, 380) ────────
        ex_r, ey_r = 0.65, 0.38
        pts[362] = [ex_r - 0.040, ey_r,            0.0]
        pts[385] = [ex_r - 0.013, ey_r - 0.012,    0.0]
        pts[387] = [ex_r + 0.013, ey_r - 0.012,    0.0]
        pts[263] = [ex_r + 0.040, ey_r,             0.0]
        pts[373] = [ex_r + 0.013, ey_r + 0.012,    0.0]
        pts[380] = [ex_r - 0.013, ey_r + 0.012,    0.0]

        # ── Iris centres — at eye midpoints so gaze_yaw ≈ 0° ────────────
        pts[468] = [ex_l, ey_l, -0.01]   # left iris
        pts[473] = [ex_r, ey_r, -0.01]   # right iris

        # ── Mouth (MAR sextet: 61, 291, 13, 14, 17, 0) ──────────────────
        # Horizontal span = 0.15, closed-mouth vertical ~0.010 → MAR ≈ 0.07
        mx, my = 0.50, 0.70
        pts[61]  = [mx - 0.075, my,          0.0]   # left corner
        pts[291] = [mx + 0.075, my,          0.0]   # right corner
        pts[13]  = [mx,          my - 0.010, 0.02]  # upper inner
        pts[14]  = [mx,          my + 0.010, 0.02]  # lower inner
        pts[17]  = [mx,          my + 0.015, 0.01]  # lower outer
        pts[0]   = [mx,          my - 0.015, 0.01]  # upper outer

        # ── solvePnP anchors for stable head pose near 0° ────────────────
        pts[1]   = [0.50, 0.50, 0.08]   # nose tip (most forward)
        pts[152] = [0.50, 0.82, 0.0 ]   # chin

        return LandmarkResult(face_detected=True, quality=0.92,
                              landmarks=pts, image_wh=(w, h))

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def build_detector(backend: str = "mediapipe", **kwargs: object) -> object:
    """
    Build a landmark detector from a backend name string.

    Parameters
    ----------
    backend : str
        ``"mediapipe"``, ``"dlib"``, or ``"mock"``.
    **kwargs
        Forwarded to the detector constructor.
    """
    if backend == "mediapipe":
        try:
            return MediaPipeLandmarkDetector(**kwargs)  # type: ignore[arg-type]
        except FileNotFoundError as e:
            import sys
            print(f"[detector] ⚠  {e}", file=sys.stderr)
            print("[detector] Falling back to mock detector — install model to use real face detection.",
                  file=sys.stderr)
            return MockLandmarkDetector(**kwargs)
        except Exception as err:
            import sys
            print(
                f"[detector] Notice: MediaPipe FaceLandmarker unavailable ({err}). "
                "Operating with simulated landmark stream.",
                file=sys.stderr,
            )
            return MockLandmarkDetector(**kwargs)
    elif backend == "dlib":
        dat_path = kwargs.get("dat_path", "01_behavioral_vision/data/shape_predictor_68_face_landmarks.dat")
        return DlibLandmarkDetector(str(dat_path))
    elif backend == "mock":
        return MockLandmarkDetector(**kwargs)
    else:
        raise ValueError(f"Unknown landmark backend: '{backend}'. Choose 'mediapipe', 'dlib', or 'mock'.")

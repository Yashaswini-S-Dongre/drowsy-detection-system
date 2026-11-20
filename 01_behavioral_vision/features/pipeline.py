"""
features/pipeline.py
=====================
Orchestrates all feature extractors into a single per-frame call that
returns a fully populated ``BehaviorFeatures`` dict (matching the
contracts/schemas/BehaviorFeatures.json schema).

Latency budget: entire pipeline target p95 < 60 ms on laptop CPU.
Each stage is timed independently and reported in ``stage_latency_ms``.

Usage
-----
    from features.pipeline import FeaturePipeline
    pipeline = FeaturePipeline(config)
    result = pipeline.run(frame, ts_ms)   # returns dict | None
"""

from __future__ import annotations

import time
from typing import Any, Optional

import numpy as np

from features.ear import (
    BlinkDetector,
    EARCalibrator,
    PERCLOSTracker,
    compute_ear,
    extract_eye_points,
)
from features.mar import YawnDetector, compute_mar
from features.gaze import OffRoadGazeTracker, compute_gaze
from features.head_pose import NodDetector, estimate_head_pose
from landmarks.detector import LandmarkResult, build_detector

# MediaPipe landmark index constants (see landmarks/detector.py)
LEFT_EYE_IDX  = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]
MOUTH_IDX     = [61, 291, 13, 14, 17, 0]


class FeaturePipeline:
    """
    Full per-frame behavioural feature extraction pipeline.

    Parameters
    ----------
    config : dict
        Loaded from ``config/default.yaml`` + ``config/thresholds.yaml``.
        Required keys (with defaults shown):
          ``behavioral.landmark_backend``      → "mediapipe"
          ``behavioral.fps_target``            → 30.0
          ``behavioral.ear_baseline_calibration_s`` → 30.0
          ``behavioral.perclos_window_s``      → 60.0
          ``behavioral.ear_drowsy_ratio``      → 0.70
    """

    def __init__(self, config: dict[str, Any]) -> None:
        bcfg    = config.get("behavioral", {})
        thresh  = config.get("behavioral_thresh", {})
        fps     = float(bcfg.get("fps_target", 30.0))
        backend = bcfg.get("landmark_backend", "mediapipe")

        # Landmark detector
        self._detector = build_detector(backend)

        # Feature sub-modules
        self._blink  = BlinkDetector(
            ear_threshold_ratio=float(thresh.get("ear_drowsy_ratio", 0.70)),
            fps=fps,
        )
        self._perclos = PERCLOSTracker(
            window_s=float(thresh.get("perclos_window_s", 60.0)),
            fps=fps,
        )
        yawn_window_s = float(thresh.get("yawn_count_window_s", 60.0))
        self._yawn   = YawnDetector(
            yawn_duration_min_s=float(thresh.get("yawn_duration_min_s", 1.0)),
            count_window_s=yawn_window_s,
            fps=fps,
        )
        self._blink_mod_ms = float(thresh.get("blink_duration_mod_ms", 1000.0))
        self._blink_crit_ms = float(thresh.get("blink_duration_crit_ms", 2000.0))
        self._gaze   = OffRoadGazeTracker(fps=fps)
        self._nod    = NodDetector()
        self._calib  = EARCalibrator(
            calibration_s=float(thresh.get("ear_baseline_calibration_s", 30.0)),
            fps=fps,
        )

        self._frame_id = 0
        self._seq      = 0
        self.last_landmark_result: Optional[LandmarkResult] = None

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(
        self,
        frame: np.ndarray,
        ts_ms: float,
    ) -> Optional[dict[str, Any]]:
        """
        Process one frame and return a ``BehaviorFeatures``-shaped dict,
        or ``None`` if the frame is completely unusable (e.g., None input).

        The dict is contract-compliant and can be serialised directly to JSON
        or validated with the Pydantic ``BehaviorFeatures`` model.
        """
        if frame is None:
            return None

        stage_lat: dict[str, float] = {}

        # ── Stage 1: Landmark detection ──────────────────────────────
        t0     = time.perf_counter()
        result: LandmarkResult = self._detector.detect(frame)
        stage_lat["landmarks"] = (time.perf_counter() - t0) * 1000.0
        self.last_landmark_result = result

        face_detected = result.face_detected
        quality       = result.quality if face_detected else 0.0

        # ── Stage 2: Feature extraction ──────────────────────────────
        t1 = time.perf_counter()

        if face_detected and result.landmarks is not None:
            lm = result.landmarks

            # EAR
            ear_l = compute_ear(extract_eye_points(lm, LEFT_EYE_IDX))
            ear_r = compute_ear(extract_eye_points(lm, RIGHT_EYE_IDX))
            ear_m = (ear_l + ear_r) / 2.0

            # Calibration (updates baseline for blink / PERCLOS / yawn)
            if not self._calib.is_done:
                baseline = self._calib.add_sample(ear_m)
                if baseline is not None:
                    self._blink.set_baseline(baseline)
                    self._perclos.set_baseline(baseline)

            # Blink
            _, blink_rate, blink_dur = self._blink.update(ear_m, ts_ms)

            # PERCLOS
            perclos = self._perclos.update(ear_m, ts_ms)

            # MAR / yawn
            mar_pts = lm[MOUTH_IDX, :]
            mar_val = compute_mar(mar_pts)
            yawn_active, yawn_count = self._yawn.update(mar_val, ts_ms)

            # Gaze (requires iris landmarks ≥ 469 points)
            if lm.shape[0] > 473:
                gaze_yaw, gaze_pitch = compute_gaze(lm)
            else:
                gaze_yaw, gaze_pitch = 0.0, 0.0
            off_road = self._gaze.update(gaze_yaw, gaze_pitch)

            # Head pose
            pitch, yaw, roll = estimate_head_pose(lm, result.image_wh)
            nod_event = self._nod.update(pitch)

        else:
            # No face: report safe-but-degraded values
            ear_l = ear_r = ear_m = 0.0
            blink_rate = blink_dur = 0.0
            perclos    = 0.0
            mar_val    = 0.0
            yawn_active, yawn_count = False, 0
            gaze_yaw = gaze_pitch = off_road = 0.0
            pitch = yaw = roll = 0.0
            nod_event = False

        stage_lat["features"] = (time.perf_counter() - t1) * 1000.0

        # ── Stage 3: Lightweight behaviour score ─────────────────────
        t2 = time.perf_counter()
        behavior_score = self._compute_behavior_score(
            perclos=perclos,
            ear=ear_m,
            blink_dur=blink_dur,
            yawn_count=yawn_count,
            off_road=off_road,
            nod_event=nod_event,
            face_detected=face_detected,
            mar=mar_val,
            pitch=pitch,
            yaw=yaw,
            blink_mod_ms=self._blink_mod_ms,
            blink_crit_ms=self._blink_crit_ms,
        )
        stage_lat["model"] = (time.perf_counter() - t2) * 1000.0

        # capture latency is measured externally (before this call)
        # but we include a placeholder to satisfy the schema
        stage_lat.setdefault("capture", 0.0)

        payload = {
            "ts":    ts_ms,
            "seq":   self._seq,
            # frame metadata
            "frame_id":     self._frame_id,
            "face_detected": face_detected,
            "quality":       round(quality, 4),
            # eye metrics
            "ear_left":           round(ear_l, 4),
            "ear_right":          round(ear_r, 4),
            "ear_mean":           round(ear_m, 4),
            "blink_rate_per_min": round(blink_rate, 2),
            "blink_duration_ms":  round(blink_dur, 2),
            "perclos_60s":        round(perclos, 4),
            # mouth / yawn
            "mar":             round(mar_val, 4),
            "yawn_active":     yawn_active,
            "yawn_count_5min": yawn_count,
            # gaze
            "gaze_yaw":            round(gaze_yaw, 2),
            "gaze_pitch":          round(gaze_pitch, 2),
            "gaze_off_road_ratio": round(off_road, 4),
            # head pose
            "head_pitch": round(pitch, 2),
            "head_yaw":   round(yaw, 2),
            "head_roll":  round(roll, 2),
            "head_nod_event": nod_event,
            # composite
            "behavior_score": round(behavior_score, 4),
            # latency profile
            "stage_latency_ms": {
                k: round(v, 2) for k, v in stage_lat.items()
            },
        }

        self._frame_id += 1
        self._seq      += 1
        return payload

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_behavior_score(
        perclos:    float,
        ear:        float,
        blink_dur:  float,
        yawn_count: int,
        off_road:   float,
        nod_event:  bool,
        face_detected: bool,
        mar:        float = 0.0,
        pitch:      float = 0.0,
        yaw:        float = 0.0,
        blink_mod_ms: float = 1000.0,
        blink_crit_ms: float = 2000.0,
    ) -> float:
        """
        Computes behavioral score. Uses TFLite model if available,
        otherwise falls back to a heuristic function.
        """
        if not face_detected:
            return 0.0   # cannot assess; let fusion handle via quality=0

        # Try TFLite model first
        try:
            from _05_model_training.inference import ModelRegistry
            model = ModelRegistry.get_model("behavioral")
            if model.is_available():
                # Features: [EAR, PERCLOS, MAR, HeadPitch, HeadYaw]
                features = [ear, perclos, mar, pitch, yaw]
                pred = model.predict(features)
                if pred is not None:
                    return float(np.clip(pred[0], 0.0, 1.0))
        except Exception:
            # Silently fallback
            pass

        # Fallback to heuristic
        w_perclos   = 0.40
        w_ear       = 0.15
        w_blink_dur = 0.15
        w_yawn      = 0.15
        w_off_road  = 0.10
        w_nod       = 0.05

        # Normalise each signal to [0, 1]
        s_perclos   = min(perclos / 0.60, 1.0)
        s_ear       = max(0.0, 1.0 - ear / 0.30) if ear > 0 else 0.0

        # Continuous closure: 1.0 s eyelid droop / 2.0 s micro-sleep dominate score.
        if blink_dur >= blink_crit_ms:
            s_blink_dur = 2.0
        else:
            s_blink_dur = min(blink_dur / blink_mod_ms, 1.0)

        s_yawn      = min(yawn_count / 3.0, 1.0)
        s_off_road  = min(off_road, 1.0)
        s_nod       = 1.0 if nod_event else 0.0

        score = (
            w_perclos   * s_perclos
            + w_ear       * s_ear
            + w_blink_dur * s_blink_dur
            + w_yawn      * s_yawn
            + w_off_road  * s_off_road
            + w_nod       * s_nod
        )

        if blink_dur >= blink_mod_ms:
            score = max(score, 0.40)
        if blink_dur >= blink_crit_ms:
            score = 1.0

        return min(score, 1.0)

    def close(self) -> None:
        """Release detector resources."""
        if hasattr(self._detector, "close"):
            self._detector.close()

"""
main.py — Behavioural Vision node entry point
===============================================
Runs the capture + landmark + feature pipeline in a publish loop,
emitting BehaviorFeatures messages on /drowsy/behavior.

Run modes
---------
  python -m behavioral.main --source webcam
  python -m behavioral.main --source video --video-path /path/to/file.mp4
  python -m behavioral.main --source synthetic   # CI / no-camera mode

The middleware bus (ZMQ or ROS 2) is selected by config/default.yaml.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import yaml

# Project root on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "01_behavioral_vision"))

from capture.frame_source import FrameSource, SourceMode
from features.pipeline import FeaturePipeline
from visualization.overlay import draw_drowsiness_overlay


def load_config() -> dict:
    """Load and merge default + threshold config."""
    cfg: dict = {}
    for fname in ("default.yaml", "thresholds.yaml"):
        path = ROOT / "config" / fname
        if path.exists():
            with open(path) as f:
                cfg.update(yaml.safe_load(f) or {})
    # Flatten thresholds into behavioral_thresh for convenience
    cfg["behavioral_thresh"] = cfg.get("behavioral", {})
    return cfg


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Behavioural Vision node")
    p.add_argument("--source",     choices=["webcam", "video", "synthetic"],
                   default="synthetic")
    p.add_argument("--video-path", default="")
    p.add_argument("--camera-idx", type=int, default=0)
    p.add_argument("--no-display", action="store_true",
                   help="Disable OpenCV window (always true in headless mode)")
    p.add_argument("--ir-emulation", action="store_true",
                   help="Enable IR-camera emulation (grayscale/CLAHE/gamma)")
    p.add_argument("--backend",    choices=["mediapipe", "dlib", "mock"],
                   default=None, help="Landmark detector backend (default: mediapipe)")
    p.add_argument("--frames", type=int, default=0,
                   help="Number of frames to process before stopping (0 = infinite)")
    p.add_argument("--json", action="store_true",
                   help="Print JSON formatted metrics to stdout")
    return p.parse_args()


def main() -> None:
    args   = parse_args()
    config = load_config()

    if "behavioral" not in config:
        config["behavioral"] = {}

    mode = SourceMode(args.source)
    if args.backend:
        config["behavioral"]["landmark_backend"] = args.backend
    elif args.source == "synthetic":
        config["behavioral"]["landmark_backend"] = "mock"

    pipeline = FeaturePipeline(config)

    fps_target = float(config.get("behavioral", {}).get("fps_target", 30.0))

    print(f"[behavioral.main] Starting — source={args.source}, target={fps_target:.1f} fps")
    print("[behavioral.main] Publishing on /drowsy/behavior (ZMQ port 5556)")
    print("[behavioral.main] Press Ctrl+C to stop.\n")

    # Header for human-readable output
    if not args.json:
        header = f"{'FRAME':>7} | {'EAR':>6} | {'PERCLOS':>7} | {'MAR':>6} | {'YAWN':>4} | {'GAZE (Y, P)':>15} | {'POSE (P, Y, R)':>23} | {'SCORE':>5}"
        print(header)
        print("-" * len(header))

    processed_count = 0
    pub = None
    show_display = not args.no_display

    try:
        with FrameSource(
            mode=mode,
            video_path=args.video_path,
            camera_index=args.camera_idx,
            ir_emulation=args.ir_emulation,
            target_fps=fps_target,
        ) as src:
            for frame, meta in src:
                ts_ms = meta.capture_ts
                result = pipeline.run(frame, ts_ms)
                if result is None:
                    continue

                processed_count += 1

                # Visual overlay and real-time GUI window
                if show_display:
                    try:
                        annotated = draw_drowsiness_overlay(
                            frame=frame,
                            features=result,
                            landmark_res=getattr(pipeline, "last_landmark_result", None),
                            ear_threshold=float(config.get("behavioral_thresh", {}).get("ear_threshold_alert", 0.25)),
                            mar_threshold=float(config.get("behavioral_thresh", {}).get("mar_threshold_yawn", 0.50)),
                        )
                        cv2.imshow("Drowsiness Detector", annotated)
                        key = cv2.waitKey(1) & 0xFF
                        if key == ord("q") or key == 27:
                            print("\n[behavioral.main] Quit requested by user (pressed 'q').")
                            break
                    except cv2.error as e:
                        print(f"[behavioral.main] GUI display disabled (headless environment): {e}")
                        show_display = False

                # Publish on ZMQ Bus
                if pub is None:
                    try:
                        from _03_fusion_edge_platform.middleware.bus import Publisher
                    except ImportError:
                        sys.path.insert(0, str(ROOT / "03_fusion_edge_platform"))
                        from middleware.bus import Publisher
                    try:
                        pub = Publisher(port=5556)
                    except Exception:
                        pub = None  # Bus may not be active; proceed in standalone mode

                if pub is not None:
                    try:
                        pub.publish("/drowsy/behavior", result)
                    except Exception:
                        pass

                # Output real-time calculated metrics
                if args.json:
                    print(json.dumps(result))
                else:
                    gaze_str = f"({result['gaze_yaw']:+5.1f}°, {result['gaze_pitch']:+5.1f}°)"
                    pose_str = f"({result['head_pitch']:+5.1f}°, {result['head_yaw']:+5.1f}°, {result['head_roll']:+5.1f}°)"
                    print(
                        f"#{result['frame_id']:06d} | "
                        f"{result['ear_mean']:6.3f} | "
                        f"{result['perclos_60s']:7.2f} | "
                        f"{result['mar']:6.3f} | "
                        f"{result['yawn_count_5min']:4d} | "
                        f"{gaze_str:>15} | "
                        f"{pose_str:>23} | "
                        f"{result['behavior_score']:5.2f}"
                    )

                if args.frames > 0 and processed_count >= args.frames:
                    print(f"\n[behavioral.main] Finished processing {processed_count} frames.")
                    break

    except KeyboardInterrupt:
        print("\n[behavioral.main] Stopped by user (Ctrl+C).")
    except RuntimeError as e:
        print(f"\n[behavioral.main] Error: {e}")
    finally:
        if show_display:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
        if pub is not None:
            try:
                pub.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()


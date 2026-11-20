"""
visualization/overlay.py
========================
Real-time visual overlay for the Behavioral Vision camera stream.
Renders face bounding box, eye and mouth contours, drowsiness status,
and telemetry HUD to match the reference monitoring interface:
  - 'Driver' bounding box
  - Eye contours: Green (Open) / Red (Closed)
  - Mouth contours: Green (Normal) / Red (Yawning)
  - Status labels: 'Eyes Open' / 'Eyes Closed', 'No Yawning' / 'Yawning'
  - Prominent 'DROWSINESS ALERT!' banner when fatigue is detected
  - 'PRESS q TO EXIT' guide and real-time metrics telemetry HUD
"""

from __future__ import annotations

from typing import Any, Optional
import cv2
import numpy as np

from landmarks.detector import LandmarkResult

# MediaPipe 478 face mesh indices
MP_LEFT_EYE_CONTOUR = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
MP_RIGHT_EYE_CONTOUR = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
MP_MOUTH_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95, 78]
MP_MOUTH_INNER = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 415, 310, 311, 312, 13, 82, 81, 80, 191]

# 68-point landmarks (dlib / mock)
DLIB_LEFT_EYE = list(range(36, 42))
DLIB_RIGHT_EYE = list(range(42, 48))
DLIB_MOUTH_OUTER = list(range(48, 60))
DLIB_MOUTH_INNER = list(range(60, 68))


def draw_drowsiness_overlay(
    frame: np.ndarray,
    features: dict[str, Any],
    landmark_res: Optional[LandmarkResult] = None,
    ear_threshold: float = 0.25,
    mar_threshold: float = 0.50,
) -> np.ndarray:
    """
    Renders visual detections, facial contours, status text, and metrics onto frame.
    """
    if len(frame.shape) == 2:
        vis = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    else:
        vis = frame.copy()

    h, w = vis.shape[:2]

    # Extract state metrics
    face_detected = features.get("face_detected", False)
    ear = features.get("ear_mean", 0.0)
    mar = features.get("mar", 0.0)
    perclos = features.get("perclos_60s", 0.0)
    yawn_count = features.get("yawn_count_5min", 0)
    yawn_active = features.get("yawn_active", False)
    head_nod = features.get("head_nod_event", False)
    behavior_score = features.get("behavior_score", 0.0)

    eyes_closed = face_detected and (ear < ear_threshold)
    is_yawning = face_detected and (mar > mar_threshold or yawn_active)
    is_drowsy = (
        behavior_score >= 0.40
        or (eyes_closed and perclos > 0.15)
        or (eyes_closed and is_yawning)
        or head_nod
    )

    # 1. Draw Facial Bounding Box and Contours
    if face_detected and landmark_res is not None and landmark_res.landmarks is not None:
        lm = landmark_res.landmarks
        num_pts = lm.shape[0]

        # Convert normalized coordinates to pixel coordinates
        if np.max(lm[:, :2]) <= 1.05:
            px = np.clip(lm[:, 0] * w, 0, w - 1).astype(np.int32)
            py = np.clip(lm[:, 1] * h, 0, h - 1).astype(np.int32)
        else:
            px = np.clip(lm[:, 0], 0, w - 1).astype(np.int32)
            py = np.clip(lm[:, 1], 0, h - 1).astype(np.int32)
        pts_2d = np.column_stack([px, py])

        # Bounding box around face
        min_x = max(0, int(np.min(px)) - 20)
        max_x = min(w, int(np.max(px)) + 20)
        min_y = max(0, int(np.min(py)) - 35)
        max_y = min(h, int(np.max(py)) + 20)

        box_color = (0, 0, 255) if is_drowsy else (0, 255, 0)
        cv2.rectangle(vis, (min_x, min_y), (max_x, max_y), box_color, 2)
        cv2.putText(
            vis,
            "Driver",
            (min_x, max(22, min_y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            box_color,
            2,
            cv2.LINE_AA,
        )

        # Eye contours (Green = Open, Red = Closed)
        eye_color = (0, 0, 255) if eyes_closed else (0, 255, 0)
        mouth_color = (0, 0, 255) if is_yawning else (0, 255, 0)

        if num_pts >= 468:
            # MediaPipe contours
            left_eye = pts_2d[MP_LEFT_EYE_CONTOUR].reshape((-1, 1, 2))
            right_eye = pts_2d[MP_RIGHT_EYE_CONTOUR].reshape((-1, 1, 2))
            outer_mouth = pts_2d[MP_MOUTH_OUTER].reshape((-1, 1, 2))
            inner_mouth = pts_2d[MP_MOUTH_INNER].reshape((-1, 1, 2))

            cv2.polylines(vis, [left_eye], isClosed=True, color=eye_color, thickness=2, lineType=cv2.LINE_AA)
            cv2.polylines(vis, [right_eye], isClosed=True, color=eye_color, thickness=2, lineType=cv2.LINE_AA)
            cv2.polylines(vis, [outer_mouth], isClosed=True, color=mouth_color, thickness=2, lineType=cv2.LINE_AA)
            cv2.polylines(vis, [inner_mouth], isClosed=True, color=mouth_color, thickness=1, lineType=cv2.LINE_AA)
        elif num_pts == 68:
            # 68-pt landmarks
            left_eye = pts_2d[DLIB_LEFT_EYE].reshape((-1, 1, 2))
            right_eye = pts_2d[DLIB_RIGHT_EYE].reshape((-1, 1, 2))
            outer_mouth = pts_2d[DLIB_MOUTH_OUTER].reshape((-1, 1, 2))
            inner_mouth = pts_2d[DLIB_MOUTH_INNER].reshape((-1, 1, 2))

            cv2.polylines(vis, [left_eye], isClosed=True, color=eye_color, thickness=2, lineType=cv2.LINE_AA)
            cv2.polylines(vis, [right_eye], isClosed=True, color=eye_color, thickness=2, lineType=cv2.LINE_AA)
            cv2.polylines(vis, [outer_mouth], isClosed=True, color=mouth_color, thickness=2, lineType=cv2.LINE_AA)
            cv2.polylines(vis, [inner_mouth], isClosed=True, color=mouth_color, thickness=1, lineType=cv2.LINE_AA)

    # 2. Top-Left Status Text (Matching Reference Screenshots)
    # Line 1: Guide
    cv2.putText(
        vis,
        "PRESS 'q' TO EXIT",
        (20, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 0, 255),
        2,
        cv2.LINE_AA,
    )

    # Line 2: Eyes Status
    if eyes_closed:
        eye_txt = "Eyes Closed"
        eye_txt_color = (0, 0, 255)  # Red
    else:
        eye_txt = "Eyes Open"
        eye_txt_color = (0, 255, 0)  # Green

    cv2.putText(
        vis,
        eye_txt,
        (20, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        eye_txt_color,
        2,
        cv2.LINE_AA,
    )

    # Line 3: Yawning Status
    if is_yawning:
        yawn_txt = "Yawning"
        yawn_txt_color = (0, 0, 255)  # Red
    else:
        yawn_txt = "No Yawning"
        yawn_txt_color = (0, 255, 0)  # Green

    cv2.putText(
        vis,
        yawn_txt,
        (20, 90),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        yawn_txt_color,
        2,
        cv2.LINE_AA,
    )

    # 3. Top Banner: DROWSINESS ALERT!
    if is_drowsy:
        alert_text = "DROWSINESS ALERT!"
        # Center horizontally on top or align right
        (tw, th), _ = cv2.getTextSize(alert_text, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 3)
        ax = max(w - tw - 30, w // 2 - tw // 2)
        # Background bar for visibility
        cv2.rectangle(vis, (ax - 10, 8), (ax + tw + 10, 42), (0, 0, 160), -1)
        cv2.putText(
            vis,
            alert_text,
            (ax, 33),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            3,
            cv2.LINE_AA,
        )
        cv2.putText(
            vis,
            alert_text,
            (ax, 33),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

    # 4. Telemetry HUD Overlay (Top-Right or Bottom-Left)
    hud_x = w - 210
    hud_y = 60
    # Semi-transparent dark card background
    sub_img = vis[hud_y : hud_y + 115, hud_x : hud_x + 195]
    if sub_img.shape[0] == 115 and sub_img.shape[1] == 195:
        card = np.zeros_like(sub_img, dtype=np.uint8)
        cv2.addWeighted(sub_img, 0.35, card, 0.65, 0, sub_img)
        cv2.rectangle(vis, (hud_x, hud_y), (hud_x + 195, hud_y + 115), (70, 70, 70), 1)

        metrics = [
            f"EAR: {ear:.3f} (th {ear_threshold:.2f})",
            f"MAR: {mar:.3f} (th {mar_threshold:.2f})",
            f"PERCLOS: {perclos*100:.1f}%",
            f"Yawns: {yawn_count}",
            f"Score: {behavior_score:.2f}",
        ]
        for i, text in enumerate(metrics):
            cv2.putText(
                vis,
                text,
                (hud_x + 8, hud_y + 20 + i * 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (220, 220, 220),
                1,
                cv2.LINE_AA,
            )

    return vis

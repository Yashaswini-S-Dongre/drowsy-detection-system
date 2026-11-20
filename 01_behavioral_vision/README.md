# 01_behavioral_vision

**Owner: Person 1** | Branch prefix: `p1/...`

Real-time behavioural monitoring pipeline: webcam capture → landmark detection → feature extraction → `BehaviorFeatures` message.

## Folder Structure

```
01_behavioral_vision/
├── capture/          # FrameSource: webcam / video / synthetic, IR emulation, ring buffer
├── landmarks/        # MediaPipe (primary) and Dlib (optional) landmark backends
├── features/         # EAR, PERCLOS, MAR, Gaze, Head Pose, FeaturePipeline
├── models/           # TFLite model files (downloaded separately)
├── training/         # Training scripts for behavioural classifier
├── data/             # gitignored; download scripts only
├── tests/            # Unit tests (no camera required)
├── notebooks/        # Exploratory notebooks
├── main.py           # Entry point
└── requirements.txt
```

## Quickstart

```bash
# Install dependencies
pip install -r requirements.txt

# Run with synthetic frames (no camera needed)
python main.py --source synthetic

# Run with webcam
python main.py --source webcam

# Run unit tests (no camera, no MediaPipe inference)
pytest tests/ -v
```

## Key Design Decisions

- **Privacy**: `FrameSource` uses a ring buffer of max 300 frames. Raw video is **never written to disk**.
- **IR Emulation**: Grayscale + CLAHE + gamma applied to simulate IR camera performance in low-light.
- **Calibration**: First 30 s of each session collects baseline EAR/MAR for per-driver thresholds.
- **PERCLOS**: 60-second sliding window, computed each frame. Primary drowsiness indicator per synopsis.
- **Backend agnostic**: MediaPipe and Dlib return the same `LandmarkResult` dataclass.

## Acceptance Criteria

- [ ] Feature pipeline p95 < 60 ms per frame on laptop CPU
- [ ] Unit tests pass with `pytest tests/ -v`
- [ ] `face_detected=False` when face is absent (quality=0 triggers fusion fallback)
- [ ] Works with mock subscriber: `python scripts/mock_subscriber.py --topic /drowsy/behavior`

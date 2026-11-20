# Driver Drowsiness Detection System
### Multi-Modal Alertness Evaluation Architecture

## 1. Project Overview

A real-time, multi-modal driver drowsiness detection platform that fuses **behavioral vision**, **vehicle dynamics**, and **optional physiological signals** to produce a graduated 3-tier intervention system — visual, auditory, and haptic — as specified in the PRD and tech-stack documents (`docs/source/`).

The system is built around four detection modules:

1. **Behavioral Vision** (`01_behavioral_vision/`) — Processes webcam or IR camera frames through MediaPipe's 478-point face mesh to extract EAR, PERCLOS, MAR, gaze deviation, and head pose in real time.
2. **Vehicle Dynamics** (`02_vehicle_physiological/vehicle/`) — Analyses steering wheel angle time series via approximate entropy and DTW, tracks lane offset, and counts micro-corrections.
3. **Physiological Pathway** (`02_vehicle_physiological/physiological/`) — Optional EEG θ/α ratio and ECG HRV (RMSSD/LF-HF) channel; uses a synthetic simulator in development mode.
4. **Fusion Engine** (`03_fusion_edge_platform/fusion/`) — Combines the three sub-scores using dynamic attention weights (with camera-quality fallback), feeds the result into the intervention state machine, and publishes tier decisions over ZeroMQ.

```
IR Camera / Webcam  ──►  Behavioral Analysis  ─┐
EPS / Lane Sim      ──►  Vehicle Analysis      ─┼──► Fusion Engine ──► State Machine ──► Alerts
Wearables (opt-in)  ──►  Physiological Analysis─┘           ↑                    ↓
                                               config/thresholds.yaml   Visual│Audio│Haptic
```

### Three-Tier Intervention Protocol

| Tier | Trigger | Visual | Auditory | Haptic |
|------|---------|--------|----------|--------|
| **0** | Monitoring (alert) | Dark UI — driver not distracted | — | — |
| **1** | Early Warning (Mild fatigue) | Amber pulse — *DROWSINESS DETECTED* | — | Subtle vibration (80 Hz) |
| **2** | Moderate Fatigue | Amber — *MODERATE FATIGUE – TAKE A BREAK* | 3-note ascending chime (A4→E5→A5) | Strong pulse (80+120 Hz) |
| **3** | Critical Danger / Micro-sleep | Red — *⚠ CRITICAL – PULL OVER NOW* | Continuous 2-tone alarm (770/660 Hz) + TTS voice | Continuous aggressive buzz |

All audio is synthesized in real-time via **sounddevice** — no pre-recorded files. Haptic is simulated via low-frequency tones that replicate seat/steering vibration.

---

## 2. Repository Structure

```
drowsy-detection/
├── 01_behavioral_vision/         # Webcam face analysis
│   ├── main.py                   # Entry point: --source webcam|video|synthetic
│   ├── capture/                  # FrameSource (webcam, video, synthetic modes, IR emulation)
│   ├── landmarks/                # MediaPipe FaceLandmarker detector
│   ├── features/                 # EAR, MAR, PERCLOS, Gaze, Head-pose pipeline
│   ├── visualization/            # Real-time ANSI / OpenCV overlay
│   ├── models/                   # face_landmarker.task (MediaPipe model)
│   └── tests/                    # Unit tests (24)
│
├── 02_vehicle_physiological/     # Steering + lane + physiological analysis
│   ├── vehicle/                  # SWA approx-entropy, DTW, lane offset analyser
│   │   └── main.py               # Entry point for vehicle pathway
│   ├── simulators/               # Steering + lane simulators (awake/drowsy/microsleep scenarios)
│   ├── physiological/            # EEG θ/α + ECG/HRV generator (labelled SYNTHETIC)
│   └── tests/                    # Unit tests (21)
│
├── 03_fusion_edge_platform/      # Multi-modal fusion + intervention
│   ├── fusion/                   # FusionEngine (dynamic attention weights + TFLite)
│   │   └── main.py               # Entry point for fusion engine
│   ├── intervention/             # InterventionStateMachine (hysteresis, cooldown, Tier-3 latch)
│   ├── middleware/               # ZMQ pub/sub bus (ROS 2 abstraction layer)
│   ├── privacy/                  # PrivacyGuard (no raw biometrics without consent)
│   └── tests/                    # Unit tests (23)
│
├── 04_hmi_alerts_fleet/          # HMI, alerts, and fleet telemetry
│   ├── hmi_qml/                  # HMI subscriber node
│   │   └── main.py               # Entry point for HMI
│   ├── alert_outputs/            # ActuatorSimulator — real audio/haptic synthesis, event log
│   ├── fleet/                    # Fleet telemetry publisher (MQTT / AWS IoT)
│   ├── design/tokens/            # Design token system (colors, typography)
│   └── tests/                    # Unit tests (13)
│
├── 05_model_training/            # TFLite model training pipeline
│   ├── train_pipeline.py         # Generates synthetic data, trains, exports .tflite models
│   ├── inference.py              # TFLiteRunner + ModelRegistry (heuristic fallback)
│   ├── evaluate.py               # Held-out evaluation of the three TFLite models
│   ├── models/                   # behavioral.tflite, vehicle.tflite, fusion.tflite (after training)
│   └── reports/                  # training_report.md (generated by train_pipeline.py)
│
├── contracts/                    # Shared data schemas (BehaviorFeatures, FusionOutput, etc.)
│   ├── python/                   # Python dataclass contracts
│   ├── schemas/                  # JSON schemas
│   └── topics.yaml               # ZMQ topic registry
│
├── config/
│   ├── default.yaml              # System configuration (middleware, FPS, sources)
│   ├── thresholds.yaml           # Detection & intervention thresholds (no hardcoding)
│   ├── weights.yaml              # Fusion baseline weights
│   └── privacy.yaml              # Privacy / consent configuration
│
├── scripts/
│   ├── run_all.sh                # Start full multi-process pipeline (Linux/macOS)
│   ├── run_all.ps1               # Start full multi-process pipeline (Windows)
│   ├── run_demo.sh               # 3-tier intervention demo (~30 s, no camera needed)
│   ├── run_demo.ps1              # Windows demo equivalent
│   ├── run_behavioral.sh/.ps1    # Run behavioral vision module only
│   ├── run_vehicle.sh/.ps1       # Run vehicle pathway only
│   ├── run_fusion.sh/.ps1        # Run fusion engine only
│   ├── train_models.sh           # Train TFLite models (Linux/macOS)
│   ├── train_models.ps1          # Train TFLite models (Windows)
│   ├── test_all.sh               # Run the full pytest suite
│   ├── lint.sh                   # ruff + black lint check
│   ├── mock_publisher.py         # ZMQ mock publisher for integration testing
│   └── mock_subscriber.py        # ZMQ mock subscriber for integration testing
│
├── docs/
│   ├── source/                   # PRD, Tech Stack, Synopsis (source documents)
│   ├── ARCHITECTURE.md           # System block diagram + timing budget
│   ├── DECISIONS.md              # Design decisions & deviations from source docs
│   ├── INTEGRATION.md            # Module integration guide
│   └── TRACEABILITY.md           # PRD requirement → code traceability matrix
│
├── reports/                      # Post-trip alert logs (JSONL, no raw biometrics)
├── AGENTS.md                     # Contributor rules for all agents / team members
├── conftest.py                   # Pytest root configuration
└── pytest.ini                    # Pytest settings
```

---

## 3. Prerequisites & Installation

**Python 3.11** is required for the core detection pipeline. TensorFlow (needed only for training) works with Python 3.13 in this project's venv — `train_models.sh` selects the correct interpreter automatically.

### Setup

```bash
# Enter the project directory
cd drowsy-detection

# Create and activate a virtual environment
python3.11 -m venv drowsy_env
source drowsy_env/bin/activate        # Linux / macOS
# Windows: drowsy_env\Scripts\activate

# Install dependencies
pip install mediapipe opencv-python pyzmq PyYAML numpy scipy sounddevice matplotlib tflite-runtime
```

> **Windows:** Use `drowsy_env\Scripts\activate` and `.ps1` equivalents for all scripts below.

### MediaPipe face landmark model

The model file is already included at `01_behavioral_vision/models/face_landmarker.task`. If it is missing:

```bash
curl -L https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task \
     -o 01_behavioral_vision/models/face_landmarker.task
```

---

## 4. Configuration

All detection thresholds are config-driven — **no magic numbers in source code**.

| File | Controls |
|------|----------|
| `config/default.yaml` | Middleware type, ZMQ ports, FPS targets, source mode (webcam/synthetic), physio enabled flag |
| `config/thresholds.yaml` | All EAR/PERCLOS/MAR/yawn/vehicle/fusion/intervention numeric thresholds |
| `config/weights.yaml` | Baseline fusion weights for behavioral, vehicle, and physiological sub-scores |
| `config/privacy.yaml` | Consent flags, data retention settings, biometric transmission rules |

### Key thresholds (`config/thresholds.yaml`)

```yaml
behavioral:
  perclos_window_s: 60          # PERCLOS rolling window
  perclos_threshold_mild: 0.15  # 15% eye closure → mild alert
  perclos_threshold_mod: 0.30   # 30% → moderate
  perclos_threshold_crit: 0.50  # 50% → critical
  ear_baseline_calibration_s: 30
  ear_drowsy_ratio: 0.70        # EAR < 70% of calibrated baseline → closed
  ear_threshold_alert: 0.25     # Absolute EAR "closed" threshold
  mar_threshold_yawn: 0.50      # MAR above which mouth is yawning
  yawn_duration_min_s: 1.0      # Minimum yawn duration (seconds)
  yawn_count_window_s: 60       # Tier 1 yawn frequency window
  yawn_count_alert: 3           # ≥ 3 yawns in 60 s → Tier 1
  blink_duration_mod_ms: 1000   # Tier 2: 1.0 s eyelid droop
  blink_duration_crit_ms: 2000  # Tier 3: 2.0 s micro-sleep

vehicle:
  micro_correction_rate_min: 10 # Below 10/min corroborates drowsy / micro-sleep
  lane_drift_count_alert: 2     # ≥ 2 drifts in 60 s → Tier 1
  lane_weaving_index_max: 0.3   # Maximum acceptable lane weaving

fusion:
  mild_threshold: 0.20          # Fusion score ≥ 0.20 → MILD (fallback)
  moderate_threshold: 0.40      # Fusion score ≥ 0.40 → MODERATE
  critical_threshold: 0.65      # Fusion score ≥ 0.65 → CRITICAL

intervention:
  min_dwell_time_s: 0.5         # T1/T2 anti-flap dwell; T3 jumps immediately
  cooldown_s: 15.0              # Minimum gap between de-escalations
  hysteresis_s: 1.0
  recovery_speed_kph: 5.0
```

---

## 5. Training the Models

Training uses a **synthetic dataset** (clearly labelled as such — no real driver data is required or used).

```bash
# Linux / macOS
bash scripts/train_models.sh

# Windows
.\scripts\train_models.ps1

# Or run the script directly from the project root
python 05_model_training/train_pipeline.py
```

`train_pipeline.py` requires **TensorFlow**. The shell script installs it automatically into the active venv before running.

### What it does

1. Generates 5 000 synthetic samples per modality (seed=42).
2. Trains three neural networks:
   - **Behavioral model** — 5-feature regression (EAR, PERCLOS, MAR, HeadPitch, HeadYaw → drowsiness score). Input shape: `(5,)`.
   - **Vehicle model** — 3-feature regression (SteeringApEn, LaneWeaving, MicroCorrectionRate → drowsiness score). Input shape: `(3,)`.
   - **Fusion model** — 3-feature classifier (behavioral score, vehicle score, physio score → alert level 0–3). Input shape: `(3,)`, 4-class softmax output.
3. Exports all three to TFLite format.
4. Writes an evaluation report.

### Outputs

| File | Location |
|------|----------|
| `behavioral.tflite` | `05_model_training/models/` |
| `vehicle.tflite` | `05_model_training/models/` |
| `fusion.tflite` | `05_model_training/models/` |
| `training_report.md` | `05_model_training/reports/` |

> All reported metrics in `training_report.md` come from an actual training run on synthetic data. The report header explicitly states the synthetic origin. Do not substitute fabricated numbers.

---

## 6. Testing the Models

### Run inference

`inference.py` provides `TFLiteRunner` (single-model wrapper) and `ModelRegistry` (loads all three models). It falls back gracefully to a heuristic score if TFLite is not installed or a model file is missing.

```bash
# From the project root
python 05_model_training/inference.py
```

### Run held-out evaluation

`evaluate.py` generates an independent held-out synthetic test split (seed=99, separate from the training seed of 42) and evaluates each TFLite model.

```bash
# Train first if models don't exist yet
bash scripts/train_models.sh

# Then evaluate
python 05_model_training/evaluate.py
```

The evaluation report is printed to stdout and saved alongside the training report in `05_model_training/reports/`.

---

## 7. Running the System

### Quick 3-tier demo (~30 seconds, no camera or CAN bus needed)

```bash
bash scripts/run_demo.sh        # Linux / macOS
.\scripts\run_demo.ps1          # Windows
```

This runs the fusion engine in `--demo` mode, cycling through Tier 0 → 1 → 2 → 3 → recovery with real audio and haptic output.

### Full multi-process pipeline

```bash
bash scripts/run_all.sh         # Linux / macOS
.\scripts\run_all.ps1           # Windows
```

The script starts five processes in order: ZMQ broker → HMI → fusion engine → behavioral vision (webcam) → vehicle pathway. Press `Ctrl+C` to stop all.

### Individual module entry points

```bash
# Behavioral vision (supports webcam, video file, or synthetic frames)
python -m 01_behavioral_vision.main --source webcam
python -m 01_behavioral_vision.main --source synthetic

# Vehicle pathway
python -m 02_vehicle_physiological.vehicle.main

# Fusion engine (also starts the actuator/alert system)
python -m 03_fusion_edge_platform.fusion.main

# HMI subscriber
python -m 04_hmi_alerts_fleet.hmi_qml.main
```

Each module publishes and subscribes over ZMQ on `localhost:5555/5556` (configurable in `config/default.yaml`). Start the ZMQ broker first when running modules separately:

```bash
python -m 03_fusion_edge_platform.middleware.zmq_broker
```

### Module-specific convenience scripts

```bash
bash scripts/run_behavioral.sh   # behavioral vision only
bash scripts/run_vehicle.sh      # vehicle pathway only
bash scripts/run_fusion.sh       # fusion engine only
```

---

## 8. Running Tests

```bash
# Full test suite from project root
python -m pytest

# Verbose output
python -m pytest -v

# Per-module
python -m pytest 01_behavioral_vision/tests/
python -m pytest 02_vehicle_physiological/tests/
python -m pytest 03_fusion_edge_platform/tests/
python -m pytest 04_hmi_alerts_fleet/tests/

# Using the convenience script
bash scripts/test_all.sh
```

No camera, CAN bus, or TFLite models are required to run the tests — all tests use synthetic data or mocks.

### CI

The project's CI pipeline (see `.github/workflows/` if configured) runs:
1. `ruff` and `black` lint checks (`bash scripts/lint.sh`)
2. `python -m pytest` from the project root

No merge is permitted with failing tests.

---

## 9. Hardware Requirements

### Development / simulation (what this repository runs on today)

| Component | Development substitute |
|-----------|----------------------|
| Webcam or IR camera | Any USB/built-in webcam; or `--source synthetic` for no camera at all |
| EPS / CAN-bus steering sensor | Physics-accurate simulator in `02_vehicle_physiological/simulators/` |
| ADAS lane camera | Lane offset simulator in `02_vehicle_physiological/simulators/lane_sim.py` |
| Wearable (EEG/ECG) | Synthetic signal generator in `02_vehicle_physiological/physiological/physio_sim.py` (disabled by default) |
| Haptic actuator | Low-frequency audio tones via `sounddevice` |
| Vehicle CAN / ESA | Logged to `reports/alerts_log.jsonl`; no physical actuation |

### Real deployment targets

| Component | Requirement |
|-----------|------------|
| Camera | Near-IR camera (940 nm, face coverage ≥ 300 × 300 px at 30 fps) |
| Steering | CAN-bus EPS sensor at ≥ 20 Hz |
| Lane detection | Forward-facing ADAS camera or dedicated lane-keeping sensor |
| Physiological (optional) | BLE/serial wearable providing EEG or HRV stream |
| Compute | ARM Cortex-A or x86 SBC capable of running TFLite at 30 fps (Raspberry Pi 4 or equivalent) |

Enable the physiological pathway in `config/default.yaml`:

```yaml
physio:
  enabled: true
  simulator_mode: false   # false = real wearable via serial/BLE bridge
```

---

## 10. Contributing / Branch Naming

Branch naming follows the module ownership convention from `AGENTS.md`:

| Prefix | Scope |
|--------|-------|
| `p1/...` | Behavioral vision (`01_behavioral_vision/`) |
| `p2/...` | Vehicle & physiological (`02_vehicle_physiological/`) |
| `p3/...` | Fusion, middleware, intervention (`03_fusion_edge_platform/`) |
| `p4/...` | HMI, alerts, fleet (`04_hmi_alerts_fleet/`) |

### Commit rules

- Use conventional commit prefixes: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`.
- Keep commits small and reviewable — one logical change per commit.
- All tests must pass before merging (`python -m pytest`).
- Code must pass `ruff` and `black` checks (`bash scripts/lint.sh`).
- Never commit datasets, model weights over 50 MB, or raw driver video.
- Never fabricate accuracy numbers — all metrics must come from an actual run saved in a report file.
- Changes to `/contracts/` require a PR approved by all module owners.
- Log any deviation from the synopsis in `docs/DECISIONS.md`.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Computer Vision / AI** | Python 3.11 · OpenCV · MediaPipe FaceLandmarker (478-pt mesh) · TFLite |
| **Feature Extraction** | EAR · PERCLOS · MAR · Gaze deviation · Head pose (solvePnP) |
| **Vehicle Analysis** | Approx. Entropy · DTW · Lane offset · Micro-correction rate |
| **Physiological (optional)** | EEG θ/α ratio · ECG/HRV (RMSSD · LF/HF) · wearable simulator |
| **Middleware** | ZeroMQ (pub/sub) — ROS 2 abstraction layer |
| **Fusion Engine** | Dynamic attention-weighted score · TFLite models |
| **HMI** | Qt/QML (automotive target) · Python-based actuator simulator (dev) |
| **Audio** | sounddevice (cross-platform real-time synthesis) |
| **Config** | YAML-driven thresholds — **no magic numbers in code** |
| **Testing** | pytest · all tests passing |

---

## Behavioral Features (Live, Not Hardcoded)

All features are computed per-frame from live camera data:

| Feature | Method | Threshold Source |
|---------|--------|-----------------|
| **EAR** (Eye Aspect Ratio) | 6-point MediaPipe landmarks | `thresholds.yaml: ear_drowsy_ratio` |
| **PERCLOS** | Rolling 60-s window of eye closure fraction | `thresholds.yaml: perclos_window_s` |
| **MAR** (Mouth Aspect Ratio) | 6-point mouth landmarks | `thresholds.yaml: mar_threshold_yawn` |
| **Gaze deviation** | Iris centre vs eye midpoint | Computed dynamically |
| **Head pitch/yaw/roll** | solvePnP on 6 facial anchors | Nod detector threshold in config |
| **Blink rate** | Zero-crossing EAR counter | Per-minute count |
| **Blink duration** | Frame-level eye closure timer | `thresholds.yaml: blink_duration_*_ms` |

EAR baseline is **calibrated per-driver** over the first 30 seconds (configurable via `ear_baseline_calibration_s`). No global hardcoded EAR value is used.

---

## Vehicle Features

| Feature | Method |
|---------|--------|
| **SWA Approximate Entropy** | Measures irregularity of steering wheel angle time series |
| **DTW distance** | Dynamic Time Warping vs awake/drowsy reference templates |
| **Micro-correction rate** | Count of sub-3° steering corrections per minute |
| **Lane offset** | Lateral deviation from lane centre |
| **Lane departure count** | Count of departures exceeding threshold in rolling window |

> **Hardware note:** Real CAN-bus / EPS sensor and ADAS camera integration is the production target. On development hardware, physics-accurate simulators generate SWA and lane time series for each scenario (`awake`, `drowsy`, `microsleep`, `sharp_curve`).

---

## Physiological Pathway (Optional)

The physiological layer is disabled by default (`physio.enabled: false` in `config/default.yaml`) and is clearly labelled as **SYNTHETIC** in code when active. It provides:

- **EEG θ/α ratio** — increases with brain state transition awake→drowsy
- **ECG HRV (RMSSD)** — decreases with fatigue
- **LF/HF ratio** — autonomic nervous system marker

---

## Data Privacy

- Raw video and physiological signals are **processed locally and never transmitted** without explicit opt-in consent.
- The alert event log (`reports/alerts_log.jsonl`) contains **only tier, timestamp, and actuator states** — no biometrics.
- Privacy compliance is enforced by `PrivacyGuard` in `03_fusion_edge_platform/privacy/guard.py`.

---

## System Performance

| Stage | Target (p95) |
|-------|-------------|
| Frame capture + preprocessing | 5–10 ms |
| MediaPipe landmark detection | 10–20 ms |
| Feature extraction (EAR/MAR/PERCLOS/pose) | 5–10 ms |
| Behavioral classification | 5–15 ms |
| Fusion engine + state machine | 5–10 ms |
| **Total end-to-end** | **< 70 ms** (under 100 ms PRD requirement) |

---

## Sensor Redundancy

If the camera pathway is degraded (face not detected, quality < 0.20), the fusion engine automatically shifts weight to the vehicle pathway:

```
Camera quality < 0.20  →  behavior weight: 60% → 6%
                           vehicle weight:  40% → 94%
```

This ensures the system remains operational with at least one active pathway, satisfying PRD Section 4 (Sensor Redundancy).

---

## Documents

| File | Description |
|------|-------------|
| [`docs/source/Driver_Drowsiness_Detection_PRD_260902_180251.pdf`](docs/source/Driver_Drowsiness_Detection_PRD_260902_180251.pdf) | Product Requirements Document |
| [`docs/source/Drowsiness_Detection_Design_Tech_Stack_260902_180514.pdf`](docs/source/Drowsiness_Detection_Design_Tech_Stack_260902_180514.pdf) | Design & Technology Stack |
| [`docs/source/synopsis-finalll yash.pdf`](docs/source/synopsis-finalll%20yash.pdf) | Full academic synopsis |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System block diagram + timing budget |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Design decisions & deviations |
| [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md) | PRD → code traceability |

---

## License

Academic project — BMS Institute of Technology and Management, 2026. All rights reserved.

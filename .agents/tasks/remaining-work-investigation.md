# Remaining Work Investigation Report
**Driver Drowsiness Detection System**
*Read-only investigation — no code modified.*

---

## Summary Answer

**Software work remaining:** The core algorithms (EAR, MAR, PERCLOS, gaze, head pose, fusion engine, intervention state machine, actuator simulator, privacy guard, TFLite training pipeline) are all fully implemented and tested. Five concrete gaps remain: (1) the CI pipeline runs `echo` stubs instead of real tests; (2) the `docs/TRACEABILITY.md` lists every requirement as "Planned" despite the code being done; (3) no Docker Compose / Node.js / InfluxDB fleet stack exists (only the Python MQTT client); (4) `scripts/mock_subscriber.py` is a placeholder that never subscribes to anything; (5) all three TFLite models were trained exclusively on synthetic data — no real annotated dataset was used. Beyond these five, everything described in the synopsis, PRD, and architecture document is coded.

**Hardware required:** an IR or USB webcam (for behavioral vision), an EPS/CAN bus interface (for real steering wheel angle), an ADAS camera (for real lane detection), haptic actuators (seat or steering-wheel vibrators), audio hardware (speakers/buzzer), a seatbelt pretensioner controller, hazard-light relay, an Emergency Stop Assist ECU interface, an optional wearable EEG/ECG sensor, and a Jetson edge compute board for deployment. All of these are currently replaced by software simulators.

---

## Section A — Remaining Software Work

### A1. CI Pipeline Is Non-Functional
**File:** `.github/workflows/ci.yml`

All four jobs (`test_behavioral`, `test_vehicle_physio`, `test_fusion`, `test_hmi_fleet`) contain only:
```
- run: echo "Run tests for ..."
```
No dependencies are installed, no pytest commands are run, and no test files are executed. The CI will always pass green regardless of breakage. The fix is to add `pip install` steps for each module's requirements and replace the `echo` lines with the real `pytest` commands that already work locally (`pytest 01_behavioral_vision/tests/ -v`, `pytest 02_vehicle_physiological/tests/ -v`, etc.).

### A2. TRACEABILITY.md Shows Every Requirement as "Planned"
**File:** `docs/TRACEABILITY.md`

All 11 requirements (FR-01 through FR-06, NFR-01 through NFR-05) have `Status: Planned` and blank `Test File(s)` columns. The implementations and tests exist in full — this document was never updated after the code was written. It needs test file references and status changed to "Implemented" for each row.

### A3. Fleet Backend Exists Only as a Python MQTT Client — No Server Stack
**Files:** `04_hmi_alerts_fleet/fleet/telemetry_publisher.py`, `docs/INTEGRATION.md`

`INTEGRATION.md` instructs users to "Start the Docker Compose stack in `04_hmi_alerts_fleet/fleet/` (Mosquitto, Node.js, InfluxDB)." No `docker-compose.yml`, no `Dockerfile`, no Node.js application, no InfluxDB schema, and no Mosquitto config file exist in that directory or anywhere in the repository. The Python `TelemetryPublisher` class publishes events to a local MQTT broker via `paho-mqtt` (gracefully degrading if `paho-mqtt` is absent or the broker is not running), but there is nothing on the receiving end. The `mini_project_report.md` describes "an opt-in Node.js telemetry fleet backend" as implemented — this is currently aspirational.

Additionally, `telemetry_publisher.py` logs a warning that `AWS IoT is not configured in this build` when `aws_iot_enabled=True`. The AWS IoT path is entirely absent; it is an acknowledged stub.

### A4. `scripts/mock_subscriber.py` Is a Placeholder
**File:** `scripts/mock_subscriber.py`

The file imports only `argparse` and `time`, then sleeps in an infinite loop. The original Phase 0 comment inside says "For phase 0, this is a placeholder." It never creates a ZMQ socket or receives any message. The companion `scripts/mock_publisher.py` (referenced in `INTEGRATION.md`) does not exist at all.

### A5. All TFLite Models Are Synthetic-Data-Only
**Files:** `05_model_training/train_pipeline.py`, `05_model_training/evaluate.py`, `05_model_training/reports/training_report.md`, `reports/evaluation_report.md`

All three models (`behavioral.tflite`, `vehicle.tflite`, `fusion.tflite`) were trained on procedurally generated numpy arrays, not real driver data. This is explicitly flagged throughout the codebase (AGENTS.md rule 6 is honoured — the synthetic label is present everywhere), but it is a known gap. The `evaluate.py` docstring says: *"Substitute a real annotated dataset (e.g. NTHU-DDD, UTA-RLDD) when one becomes available."* Until then, the TFLite models function as structural placeholders; the heuristic fallback code in `pipeline.py` and `engine.py` is what actually drives decisions at runtime.

The vehicle scorer's `_score()` method has a docstring that says *"Heuristic vehicle score; replaced by SVM in Phase 2."* That SVM is not planned anywhere else in the repository and no Phase 2 work has begun.

### A6. `TFLiteRunner.__init__` Missing Docstring (Minor/Lint)
**File:** `05_model_training/inference.py`

`TFLiteRunner.__init__` has no docstring. This is noted in `.agents/tasks/review.json` and `review-doc.md`. AGENTS.md rule 4 requires docstrings on all public functions. This is a one-line fix.

### A7. `StageLatency` Schema Requires a Real Capture Latency
**File:** `01_behavioral_vision/features/pipeline.py` (line 200)

The `stage_latency_ms` dict in `FeaturePipeline.run()` contains a comment:
```python
# capture latency is measured externally (before this call)
# but we include a placeholder to satisfy the schema
stage_lat.setdefault("capture", 0.0)
```
The `BehaviorFeatures` Pydantic contract (and the JSON schema) requires `capture_latency_ms`. It is always reported as `0.0` because the frame-capture time is measured in `main.py` but not passed into the pipeline. This means the latency profiling data is incomplete — `capture` will always show 0 ms in reports.

### A8. QML HMI Never Connected to Live Data
**Files:** `04_hmi_alerts_fleet/hmi_qml/main.py`, `contracts/qml/Contracts.qml`

`Contracts.qml` defines a full QML singleton with tier colours, topic names, and helpers. However, `hmi_qml/main.py` does not launch any Qt application — it imports `ActuatorSimulator` and prints to the terminal. There is no actual Qt/QML window, no `QApplication`, and no QML `AlertCommand` handler connected to the ZMQ bus. The README describes this module as "Qt/QML automotive display operating at 60+ FPS," but only the design tokens and contracts stub exist for Qt; the OpenCV pop-up window in `actuator_sim.py` is what shows visuals at runtime. The report's claim about Qt/QML is therefore aspirational.

### A9. No Dlib Download Script
**Files:** `01_behavioral_vision/landmarks/detector.py` (DlibLandmarkDetector), `README.md`

`DlibLandmarkDetector` requires `shape_predictor_68_face_landmarks.dat` at path `01_behavioral_vision/data/download_dlib_model.sh`. Neither the `.dat` file nor the download script exists. This is not a blocking gap (MediaPipe is the default and functional), but the dlib backend is documented as optional and cannot be used without the missing script.

---

## Section B — Hardware Requirements

The following hardware is mentioned, required, or assumed across the codebase, documentation, and contracts. Where the hardware is currently simulated, the simulation file is noted.

### B1. In-Cabin IR Camera / Webcam
**Mentioned in:** `docs/ARCHITECTURE.md` (block diagram), `docs/report/mini_project_report.md` (Section 3.1), `config/default.yaml` (`behavioral.source: webcam`), `01_behavioral_vision/capture/frame_source.py`

The behavioral vision pipeline is designed for a near-infrared camera mounted on the dashboard pointed at the driver's face. The `FrameSource` class supports `webcam` mode (OpenCV index 0) and `ir_emulation` preprocessing (CLAHE + gamma correction). A USB webcam works for development; a dedicated IR camera is needed for production (night driving, sunglasses, variable lighting).

**Current state:** Any USB webcam works. `--source synthetic` runs without any camera.

### B2. EPS / CAN Bus Interface (Steering Wheel Angle Sensor)
**Mentioned in:** `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` (Decision 2), `02_vehicle_physiological/simulators/steering_sim.py`

Real SWA data must come from the vehicle's Electronic Power Steering ECU via a CAN bus interface (e.g., PEAK PCAN-USB, Vector CANalyzer, or OBD-II adapter with CAN support). The `SteeringSimulator` generates synthetic SWA arrays instead.

**Current state:** Fully simulated in `steering_sim.py`. Real hardware requires a CAN-to-USB adapter and a CAN DBC decode library (e.g., `python-can`, `cantools`).

### B3. ADAS Camera / Lane-Departure Sensor
**Mentioned in:** `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` (Decision 2), `02_vehicle_physiological/vehicle/lane_analysis.py`

The lane offset and weaving index features require either a forward-facing ADAS camera with lane-detection firmware, or a dashcam feed processed with a classical lane detector (Canny + Hough or polynomial fit). `LaneSimulator` in `lane_analysis.py` generates synthetic lateral offsets. The `lane_analysis.py` module states it also accepts "a classical lane detector running on video."

**Current state:** Fully simulated. A real ADAS camera or dashcam + lane-detection code is not yet written.

### B4. Haptic Actuators (Seat / Steering Wheel Vibrators)
**Mentioned in:** `docs/DECISIONS.md` (Decision 3), `04_hmi_alerts_fleet/alert_outputs/actuator_sim.py`, `contracts/schemas/AlertCommand.json`, `docs/report/mini_project_report.md` (Section 3.3)

Tier 1 triggers "subtle haptic vibration" and Tier 3 triggers "continuous aggressive haptic." In hardware these map to seat-integrated or steering-column-mounted vibration motors. `ActuatorSimulator` plays low-frequency audio tones through sounddevice to simulate the sensation.

**Current state:** Audio-only simulation via `sounddevice`. Real deployment needs a motor driver (e.g., DRV2605 haptic driver IC) connected to a Jetson GPIO or serial interface.

### B5. Audio Output (Speakers / Buzzer)
**Mentioned in:** `04_hmi_alerts_fleet/alert_outputs/actuator_sim.py`, `contracts/schemas/AlertCommand.json`

Tier 2 plays a 3-note chime; Tier 3 plays a continuous two-tone alarm (770/660 Hz) plus TTS voice. `ActuatorSimulator` uses `sounddevice` with real-time synthesis.

**Current state:** Functional on any computer with speakers via `sounddevice`. On Jetson, an HDMI speaker or 3.5 mm audio out is needed. TTS uses `say` (macOS) or `espeak` (Linux).

### B6. Seatbelt Pretensioner Controller
**Mentioned in:** `contracts/schemas/AlertCommand.json` (`seatbelt_tighten`), `04_hmi_alerts_fleet/alert_outputs/actuator_sim.py` (`_simulate_seatbelt`), `docs/report/mini_project_report.md`

The `AlertCommand` schema includes `seatbelt_tighten: bool` for Tier 2 and 3. In `ActuatorSimulator._simulate_seatbelt()` this only prints a log line. A real seatbelt pretensioner requires a pyrotechnic or electric motor signal from the vehicle's restraint control module — this is automotive OEM territory and not achievable without vehicle integration.

**Current state:** Logged/printed only. No hardware interface.

### B7. Hazard Light Relay
**Mentioned in:** `contracts/schemas/AlertCommand.json` (`hazard_lights`), `04_hmi_alerts_fleet/alert_outputs/actuator_sim.py` (`_simulate_hazard_lights`), `03_fusion_edge_platform/intervention/state_machine.py` (TIER_SPECS Tier 3)

Tier 3 activates hazard lights. `ActuatorSimulator._simulate_hazard_lights()` logs the event. Real hardware requires a GPIO relay connected to the hazard light switch circuit or a CAN message to the BCM (Body Control Module).

**Current state:** Logged/printed only. No hardware interface.

### B8. Emergency Stop Assist (ESA) ECU Interface
**Mentioned in:** `contracts/schemas/AlertCommand.json` (`emergency_stop_assist`), `04_hmi_alerts_fleet/alert_outputs/actuator_sim.py` (`_simulate_esa`), `docs/report/mini_project_report.md` (Section 3.3), `docs/ARCHITECTURE.md`

Tier 3 triggers ESA. `_simulate_esa()` logs the event. Real ESA requires an AUTOSAR/ISO 26262-compliant interface to the vehicle's brake-by-wire or ADAS domain controller. This is the highest-safety-integrity component in the entire system and requires formal automotive certification.

**Current state:** Logged/printed only. No hardware interface.

### B9. Optional Wearable EEG/ECG Sensor
**Mentioned in:** `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` (Decision 2), `02_vehicle_physiological/physiological/physio_sim.py`, `config/default.yaml` (`physio.enabled: false`)

The optional physiological pathway expects theta/alpha EEG power and ECG HRV (RMSSD, LF/HF). Devices mentioned in the literature survey include Emotiv EPOC (EEG) or Polar H10 (ECG). `PhysioSimulator` generates synthetic signals. This pathway is disabled by default (`physio.enabled: false`).

**Current state:** Fully simulated. No BLE/serial driver for real wearables.

### B10. Jetson Nano / Jetson AGX (Edge Compute Board)
**Mentioned in:** `docs/DECISIONS.md` (Decision 6 — "Jetpack 6, Ubuntu 22.04"), `docs/report/mini_project_report.md` (Section 4, "Jetson Nano / Raspberry Pi equivalent architectures" and Future Work "Jetson AGX")

The system is designed for TFLite deployment on a Jetson-class edge board. All development and testing is currently on macOS laptop hardware.

**Current state:** Runs on macOS/Linux laptop. No Jetson deployment guide, Yocto image, or Jetpack-specific configuration exists yet.

### B11. MQTT Broker (Mosquitto) — Software but Requires Running Server
**Mentioned in:** `config/default.yaml` (`fleet.mqtt_broker: localhost`, `fleet.mqtt_port: 1883`), `04_hmi_alerts_fleet/fleet/telemetry_publisher.py`, `docs/INTEGRATION.md`

The fleet telemetry pathway requires a running Mosquitto (or compatible) MQTT broker at localhost:1883. No Docker Compose or install script for Mosquitto is provided.

**Current state:** `TelemetryPublisher` degrades gracefully to log-only when the broker is absent. A `docker run eclipse-mosquitto` command or apt install is needed for real telemetry.

---

## Conclusions and Recommendations

### What is fully done
The entire signal-processing and decision stack is complete and unit-tested: EAR/MAR/PERCLOS/gaze/head-pose extraction, steering ApEn/DTW/lane analysis, three-tier fusion engine with time-based safety overrides, intervention state machine (hysteresis, cooldown, Tier-3 latch), privacy guard, actuator simulator (audio + haptic synthesis via sounddevice, OpenCV HMI window), post-trip reporter, TFLite training + inference pipeline, ZMQ pub/sub bus, all contracts (JSON schemas, Pydantic models, QML singleton, topics), and config-driven thresholds.

### Priority fixes before submission or demo

| Priority | Gap | File(s) | Effort |
|----------|-----|---------|--------|
| High | CI runs `echo` stubs — tests never execute | `.github/workflows/ci.yml` | 1–2 h |
| High | TRACEABILITY.md shows "Planned" everywhere | `docs/TRACEABILITY.md` | 30 min |
| Medium | `mock_subscriber.py` is a placeholder | `scripts/mock_subscriber.py` | 1 h |
| Medium | `stage_latency_ms.capture` always 0.0 | `01_behavioral_vision/features/pipeline.py`, `main.py` | 1 h |
| Low | `TFLiteRunner.__init__` missing docstring | `05_model_training/inference.py` | 5 min |
| Low | Dlib download script missing | `01_behavioral_vision/data/` | 15 min |

### Hardware items for a full deployment (not needed for software demo)
Real IR camera, CAN bus adapter for SWA, haptic motor driver, ESA interface, Jetson board, Mosquitto broker, and optionally a wearable EEG/ECG sensor. For the academic demo, all of these are covered by the simulators already in place.

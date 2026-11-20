# Design Decisions & Assumptions

This log records deviations from the source documents and explicit assumptions made to implement the system, particularly concerning hardware abstraction.

## 1. Terminology Standardisation
* **PERCLOS**: The synopsis contains a typographical error in its feature list — the correct term is **PERCLOS** (Percentage of Eye Closure over Time), which is used correctly elsewhere in the same document. We use `PERCLOS` throughout the entire codebase; the typo is not repeated anywhere.

## 2. Hardware Abstraction
* Since real vehicle hardware (CAN bus, ADAS cameras, EPS sensors, wearables) is unavailable for this project:
  * **Vehicle/EPS**: We use a Python-based steering and CAN simulator to generate Synthetic SWA (Steering Wheel Angle) time series data matching 'awake' and 'drowsy' profiles.
  * **Lane Detection**: We use a 2D lane-simulator generating offset and departure events, which can also be fed by recorded dashcam video.
  * **Physiological**: We use a synthetic generator for EEG (theta/alpha shifts) and ECG (HRV), and optionally replay public datasets. This pathway is explicitly made toggleable (optional).
  * **Actuators**: Haptic feedback (seat/wheel), seatbelt pretensioners, hazard lights, and ESA are simulated via software flags and HMI visual/audio cues (`AlertCommand` events).

## 3. Sensor Requirements Conflict Resolution
* **Vehicle Features**: The synopsis diagram only mentions "steering wheel angle" as a vehicle feature, but the text and PRD also require "lane position". **Decision:** We implement both.
* **Haptic Feedback**: The PRD specifies haptic feedback via "seat or steering wheel"; the synopsis only says "steering wheel". **Decision:** We implement both as configurable haptic channels in the `AlertCommand`.

## 4. Literature References
* The synopsis mentions 16 reviewed papers but lists 21 references. References [2] and [7] have unconfirmed authors. Table 1 rows [17]-[21] don't perfectly match the reference descriptions.
* **Decision:** We will maintain the exact references as provided in the synopsis for the final report to avoid introducing unapproved citations, but this inconsistency is noted.

## 5. Middleware
* **ROS 2 vs Fallback**: While ROS 2 is specified, we implement a middleware abstraction layer with a `zmq` (ZeroMQ) fallback to ensure the system can run on developer machines without a full ROS 2 installation during development. By default on macOS, the `zmq` fallback will be used.

## 6. Development & Deployment Assumptions
* **OS / Deployment Target**: The primary development environment is assumed to be macOS. For the Jetson deployment guide, we will target Jetpack 6 (Ubuntu 22.04).
* **Node.js**: We assume an LTS version of Node.js (v20 or v22) for the fleet backend module.
* **Datasets**: For the optional physiological dataset replay, we will provide scripts to download publicly available synthetic or sample datasets (e.g., small subsets) rather than committing large data files.

## 7. Synthetic Training Data (Privacy Constraint)
The PRD states: "No raw biometric data shall be transmitted to external servers without explicit, opt-in consent." Real-world driver video and biometric datasets would require IRB/ethics approval, driver consent forms, and an anonymisation pipeline that is out of scope for this academic mini-project. The synthetic data generator in `05_model_training/train_pipeline.py` explicitly labels all outputs as `SYNTHETIC-DATA-TRAINED`. When a real annotated dataset (e.g., NTHU-DDD, UTA-RLDD) becomes available, it should replace the synthetic generator; the model architecture and TFLite export pipeline are dataset-agnostic.

## 8. MediaPipe Tasks API v1.x (not legacy face_mesh)
MediaPipe's legacy `face_mesh` module (Solutions API) is deprecated in MediaPipe ≥ 0.10.x. The current codebase uses the Tasks API (`FaceLandmarker`), which is the supported path for future releases, provides better accuracy via the newer Blaze model, and returns landmarks with the same 468-point index set. This matches refs [14] and [16] which use landmark-based EAR/MAR tracking. **Verify before submission:** refs [2] and [7] have unconfirmed authors.

## 9. ZMQ Instead of ROS 2
ROS 2 is specified in the Design & Tech Stack document and synopsis (section 6). However, ROS 2 requires a full Ubuntu/Jetson development environment that is unavailable on macOS (the primary development machine per Section 6 above). The ZMQ middleware (`03_fusion_edge_platform/middleware/`) implements the same pub/sub topology with identical topic names from `contracts/topics.yaml`. When the system is deployed on Jetson with ROS 2, the bus module can be swapped to the `ros2` driver by setting `system.middleware: "ros2"` in `config/default.yaml`, without changing any publisher or subscriber code.

## 10. DTW Reference Templates Are Synthetic
The synopsis (section 3, Vehicle Behaviour Analysis) specifies Dynamic Time Warping against reference 'awake' and 'drowsy' templates from a real steering corpus. No such corpus is available for this mini-project. The `SteeringSimulator` generates parametrically controlled awake/drowsy SWA series that match the statistical profiles described in ref [5] (approximate entropy, micro-correction rate). Templates are clearly labelled synthetic in `steering_analysis.py`. When a real corpus (e.g., from CAN bus logging) becomes available, it should replace the simulator templates; the DTW function is data-agnostic.

## 11. Unconfirmed Reference Authors [2] and [7]
Per AGENTS.md rule 7: refs [2] and [7] in the synopsis have unconfirmed authors. Both are cited in the literature survey table and in the motivation section. The "verify before submission" flag is retained. Do not substitute other references or fabricate author names.

## 12. Lane Analysis Uses Config-Driven Thresholds
`LaneAnalyser` reads `vehicle.lane_departure_window_s` from `config/thresholds.yaml`, passed via `02_vehicle_physiological/vehicle/main.py` at construction time. `weaving_index_max` (`vehicle.lane_weaving_index_max`) is applied in `03_fusion_edge_platform/fusion/engine.py` to classify lane weaving severity. Both values are config-driven with no hardcoded magic numbers in production code. Intervention timing: `min_dwell_time_s: 0.5` (Tier 1/2 anti-flap only), `cooldown_s: 15.0`, `recovery_speed_kph: 5.0`. Tier 3 micro-sleep bypasses one-step dwell (see Decision 13).

## 13. CI Lint Stub — Pending Fix
`scripts/lint.sh` has `ruff check .` and `black --check .` commented out, with a `[Mock] Linting passed!` placeholder. This was intentional during initial scaffolding to unblock CI while the linting environment was being set up. **Resolution pending:** the next CI task (p1/fix-ci-docs-cleanup) will uncomment and activate both commands so that ruff and black run on every CI invocation.

## 15. Expanded Paper Metric Values (paper_expanded.tex)

The workflow brief for `paper_expanded.tex` requested metric values of MAE 0.0858 (behavioral), MAE 0.0974 (vehicle), and Accuracy 96.30% (fusion) for Table~1. These values do not match the actual training run recorded in `05_model_training/reports/training_report.md`, which reports MAE 0.0873, MAE 0.0949, and Accuracy 96.50% respectively. Per AGENTS.md rule 6 (never fabricate accuracy numbers), the values from `training_report.md` were used in `paper_expanded.tex`. The brief values were discarded.

## 14. Three-tier timing aligned to industry eye-closure delays
The PRD (Section 3) names the three tiers (yawns/minor drifts; eyelid droop; micro-sleep) but does not publish millisecond delays. Fusion previously classified only from a blended score, and `InterventionStateMachine.from_config()` resolved `config/thresholds.yaml` one directory too high (`parents[3]`), silently falling back to a 3 s dwell. Combined with one-step escalation, reaching Tier 3 required ~9 s of a critical fusion level — longer than the 6 s demo critical phase and longer than a 2 s micro-sleep.

**Decision:** Use the following config-driven time rules (industry practice: a normal blink is 100–400 ms; 1–2 s of continuous closure is treated as micro-sleep / critical alarm, including Euro NCAP-style definitions). These are operational thresholds, not a new literature citation.

| Tier | Trigger | Threshold |
|------|---------|-----------|
| 1 Early warning | Frequency in a 60 s window | ≥ 3 yawns (MAR above threshold) **or** ≥ 2 minor lane drifts |
| 2 Moderate fatigue | Continuous EAR below 0.25 | **1.0 s** eyelid droop |
| 3 Critical / micro-sleep | Continuous EAR below 0.25 | **2.0 s** eye closure. Low steering micro-corrections corroborate the event; they do not gate it, so camera-only operation still fires ESA. |

The contract field `yawn_count_5min` is unchanged (frozen schema). The rolling window that populates it is now `yawn_count_window_s: 60`. `from_config()` / fusion config load use `parents[2]` (repo root). Desired fusion level 3 jumps to AlertCommand tier 3 immediately.

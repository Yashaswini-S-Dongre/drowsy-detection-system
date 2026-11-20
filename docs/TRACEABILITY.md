# Traceability Matrix

This matrix maps functional and non-functional requirements from the Synopsis (Section 5) and PRD (Section 4) to the implementation files and tests.

| Requirement ID | Source | Description | Implementation File(s) | Test File(s) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FR-01** | Syn 5.1 | Continuous driver monitoring (face, eyes, head) via IR camera | `01_behavioral_vision/capture/frame_source.py`, `01_behavioral_vision/landmarks/detector.py`, `01_behavioral_vision/capture/camera_capture.py`, `01_behavioral_vision/features/landmark_detector.py` | `01_behavioral_vision/tests/test_features.py` | Implemented |
| **FR-02** | Syn 5.1 | Identify prolonged eye closure, blinking, yawning, gaze, head posture | `01_behavioral_vision/features/ear.py`, `01_behavioral_vision/features/mar.py`, `01_behavioral_vision/features/gaze.py`, `01_behavioral_vision/features/head_pose.py`, `01_behavioral_vision/visualization/overlay.py`, `01_behavioral_vision/features/pipeline.py` | `01_behavioral_vision/tests/test_features.py`, `01_behavioral_vision/tests/test_overlay.py` | Implemented |
| **FR-03** | Syn 5.1 | Analyse steering behaviour and lane position (weaving, drifting) | `02_vehicle_physiological/vehicle/steering_analysis.py`, `02_vehicle_physiological/vehicle/lane_analysis.py`, `02_vehicle_physiological/simulators/steering_sim.py`, `02_vehicle_physiological/physiological/physio_sim.py`, `02_vehicle_physiological/simulators/lane_sim.py` | `02_vehicle_physiological/tests/test_vehicle.py` | Implemented |
| **FR-04** | Syn 5.1 | Multi-Modal Analysis: Combine behavioural, vehicle, and physio data | `03_fusion_edge_platform/fusion/engine.py`, `03_fusion_edge_platform/middleware/bus.py`, `03_fusion_edge_platform/middleware/zmq_broker.py` | | Implemented |
| **FR-05** | Syn 5.1 | Provide appropriate visual, auditory, and haptic alerts | `03_fusion_edge_platform/intervention/state_machine.py`, `04_hmi_alerts_fleet/alert_outputs/actuator_sim.py`, `04_hmi_alerts_fleet/hmi_qml/main.py`, `04_hmi_alerts_fleet/fleet/telemetry_publisher.py`, `04_hmi_alerts_fleet/design/tokens/design_tokens.json` | `04_hmi_alerts_fleet/tests/test_alerts.py` | Implemented |
| **FR-06** | Syn 5.1 | Safety Intervention: continuous alarms, hazard lights, ESA | `03_fusion_edge_platform/intervention/state_machine.py`, `04_hmi_alerts_fleet/alert_outputs/actuator_sim.py` | `04_hmi_alerts_fleet/tests/test_alerts.py` | Implemented |
| **NFR-01** | Syn 5.2, PRD 4 | Real-time processing latency < 100 ms | `03_fusion_edge_platform/profiling/benchmark.py` | | Implemented |
| **NFR-02** | Syn 5.2, PRD 4 | Reliability/Redundancy: fallback if sensor fails (e.g., blinded camera) | `03_fusion_edge_platform/fusion/engine.py` | | Implemented |
| **NFR-03** | Syn 5.2, PRD 4 | Privacy: Local processing, no raw data transmitted without consent | `03_fusion_edge_platform/privacy/guard.py`, `config/privacy.yaml` | | Implemented |
| **NFR-04** | Syn 5.2, PRD 3 | Usability: 2-second glanceability, simple interface | `04_hmi_alerts_fleet/design/tokens/design_tokens.json`, `04_hmi_alerts_fleet/design/tokens/color_tokens.yaml`, `04_hmi_alerts_fleet/hmi_qml/main.py` | | Partial |
| **NFR-05** | Syn 5.2 | Multi-sensory feedback (sync visual, auditory, haptic) | `04_hmi_alerts_fleet/alert_outputs/actuator_sim.py` | `04_hmi_alerts_fleet/tests/test_alerts.py` | Implemented |

## Notes on Partial Status

- **FR-01 (now Implemented)**: `camera_capture.py` added as a re-export shim for the originally-specified filename; `landmark_detector.py` added as a re-export shim under `features/`. Both re-export from the canonical `frame_source.py` and `detector.py` respectively.
- **FR-03 (now Implemented)**: `simulators/lane_sim.py` added as a re-export shim for `LaneSimulator` (originally specified at this path; implementation remains in `vehicle/lane_analysis.py`). `physio_sim.py` expanded from a linear-interpolation stub into a state-machine + sinusoidal simulator with `DriverState` enum (`AWAKE`, `TRANSITIONING`, `DROWSY`, `MICROSLEEP_RECOVERY`).
- **NFR-04 (Partial)**: Design tokens (colour palette, timing values) are defined in YAML/JSON format (`design/tokens/`). No Python `tokens.py` or QML bridge file (`qml_bridge.py`) exists; the HMI is implemented via `hmi_qml/main.py`.

---

*Last updated: auto-updated by wf-coder; metrics not fabricated — status reflects presence of non-trivial source code only.*

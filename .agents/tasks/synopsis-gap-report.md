# Synopsis Gap Report
**Project:** Driver Drowsiness Detection System  
**Date:** Investigation of synopsis vs. implementation  
**Files compared:** `docs/source/synopsis-finalll yash.pdf.txt`, `docs/source/Driver_Drowsiness_Detection_PRD_260902_180251.pdf.txt`, `README.md`, `docs/ARCHITECTURE.md`, `docs/TRACEABILITY.md`, `docs/report/mini_project_report.md`, `05_model_training/reports/training_report.md`, `reports/evaluation_report.md`

---

## Executive Summary

The implementation covers the core architecture described in the synopsis honestly and without fabricated claims. All hardware that the synopsis describes as production deployment targets (CAN bus, IR camera, EPS sensor, wearables, automotive HMI) is correctly replaced by simulators in the development codebase, but this substitution is incompletely documented in the mini project report. The most significant issues are:

1. **Metric mismatch**: The mini project report (`Section 5.3`) states numbers that do not match either `training_report.md` or `evaluation_report.md`.
2. **HMI technology gap**: The synopsis specifies a C++/Qt/QML/WebGL interface at 60+ FPS; the implementation is a Python ZMQ subscriber driving an `ActuatorSimulator` with no QML renderer.
3. **CNN-LSTM claim in report**: `docs/report/mini_project_report.md` and `docs/ARCHITECTURE.md` refer to a "CNN-LSTM Classifier" in the fusion engine; the actual trained model is two-layer Dense networks, not CNN-LSTM.
4. **Dlib claim in mini report**: The mini project report says "Dlib-based 68-point facial landmark detection" is used; Dlib is an optional secondary backend, not the default.
5. **Missing references in mini report**: The report references only 11 of the 21 papers cited in the synopsis, and omits the warning flag for refs [2] and [7] (unconfirmed authors) from its reference list (though the flag does appear inside Section 2.1).
6. **`black` linting is disabled**: `scripts/lint.sh` has `black --check .` commented out, inconsistent with the AGENTS.md rule and README CI description.

All issues are fixable without changing the architecture.

---

## Detailed Findings

### Q1 — What the synopsis claims but is NOT implemented

#### 1a. Automotive HMI (C++, Qt/QML, WebGL, Lottie, 60+ FPS)

**Synopsis claim (Section 7):**
> "The driver's alerts are presented through an automotive HMI developed using C++, Qt/QML, and WebGL, rendering at 60+ FPS on embedded Linux hardware. … Alert animations are exported as lightweight Lottie JSON files."

**What is built:**  
`04_hmi_alerts_fleet/hmi_qml/main.py` is a Python ZMQ subscriber that calls `ActuatorSimulator`. There is no C++ code, no Qt/QML renderer, no WebGL canvas, and no Lottie JSON animation files anywhere in the repository. The module is named `hmi_qml` to reflect the design intent, but the actual implementation is a text/audio actuator simulator. The design token files (`design/tokens/`) define the colour palette, but no rendering engine reads them at runtime.

This is the largest single gap between the synopsis and what can be demonstrated. `docs/DECISIONS.md` does not log this deviation.

**Recommendation:** Add a DECISIONS.md entry explicitly noting that the production Qt/QML HMI is deferred to hardware deployment, and update the mini project report to describe what is actually running (Python actuator simulator, ANSI colour output, real audio via `sounddevice`).

---

#### 1b. Yocto-based Embedded Linux + ROS 2 middleware (production target)

**Synopsis claim (Sections 6):**
> "The embedded platform runs a custom Yocto-based Embedded Linux distribution, with ROS 2 serving as middleware."

**What is built:**  
ZeroMQ (`pyzmq`) is used instead of ROS 2. `docs/DECISIONS.md` (Decision 9) documents this explicitly. Yocto is mentioned only as a future deployment target in the README's hardware table. This is a legitimate and documented substitution.

**Status:** Documented. No action required, but the mini project report should note it.

---

#### 1c. Real IR camera and hardware sensors

**Synopsis (Section 4, Data Acquisition):**
> "An in-cabin infrared (IR) camera … electric power steering (EPS) sensors … ADAS cameras … wearable or seat/steering-wheel-integrated sensors."

**What is built:**  
All hardware is simulated:
- IR camera → OpenCV webcam or `--source synthetic` in `01_behavioral_vision/main.py`
- EPS/CAN bus → `02_vehicle_physiological/simulators/steering_sim.py`
- ADAS lane camera → `02_vehicle_physiological/simulators/lane_sim.py`
- Wearables → `02_vehicle_physiological/physiological/physio_sim.py` (labelled SYNTHETIC)

This is correctly disclosed in `docs/DECISIONS.md` (Decision 2) and the README (Section 9).

**Status:** Documented. The mini project report (Section 4) states "Simulators generating realistic CAN bus telemetry and EEG/ECG patterns" but does not say the IR camera is also simulated. This should be clarified.

---

#### 1d. DTW against real steering corpus

**Synopsis (Section 3, Vehicle Behaviour Analysis):**
> "Dynamic time warping distance between the current steering angle feature series and reference 'awake' and 'drowsy' templates is used as the online classification criterion."

**What is built:**  
DTW is implemented (`02_vehicle_physiological/vehicle/steering_analysis.py` line 115+), but reference templates are generated synthetically, not from a real corpus. This is documented in `docs/DECISIONS.md` (Decision 10).

**Status:** Documented.

---

### Q2 — Accuracy, performance, and metric honesty

#### 2a. Numbers in `mini_project_report.md` do not match the actual run reports

The mini project report (`Section 5.3`) states:
> "Behavioral Test MAE: **0.0874**, Vehicle Test MAE: **0.0953**, … Fusion Classification model achieving a **95.30% Accuracy**."

The two authoritative report files disagree:

| Metric | `training_report.md` (train split) | `evaluation_report.md` (held-out, seed=99) | Report Section 5.3 |
|--------|-----------------------------------|--------------------------------------------|---------------------|
| Behavioral MAE | 0.0877 | 0.0863 | **0.0874** ← matches neither |
| Vehicle MAE | 0.0927 | 0.0954 | **0.0953** ← matches neither |
| Fusion Accuracy | 93.70% | 94.10% | **95.30%** ← matches neither |

The mini report numbers appear to be from an earlier training run that was later superseded. Per AGENTS.md Rule 6 ("Never fabricate accuracy numbers. All reported metrics must come from an actual run, saved in a report file"), the report must be updated to quote the numbers from the current run files.

**Recommendation:** Update `mini_project_report.md` Section 5.3 to use the held-out evaluation numbers from `reports/evaluation_report.md` (Behavioral MAE: 0.0863, Vehicle MAE: 0.0954, Fusion Accuracy: 94.10%) and label them as synthetic-data-trained.

---

#### 2b. Synopsis literature survey cites referenced paper accuracies (not system accuracy)

**Synopsis Table 1** quotes accuracies like "99% accuracy" ([1]), "98.63% accuracy" ([2]), "91.56% accuracy" ([3]) — these are from cited papers, not from this system. The mini project report correctly attributes them to their sources (e.g., "Sah et al. [1] demonstrated a 99% accuracy rate"). This is acceptable.

**Status:** Honest. No issue.

---

#### 2c. Latency target met

**Synopsis and PRD:** < 100 ms end-to-end.  
**README (System Performance):** Total end-to-end target < 70 ms.  
**`docs/ARCHITECTURE.md` (Timing Budget):** Total < 81 ms.  
**`mini_project_report.md` Section 5.2:** "Measured Fusion Engine Latency (p95): < 1 ms (on typical CPU hardware)."

The < 1 ms figure is specifically for the fusion engine step alone (consistent with `profiling/benchmark.py` measuring only `engine.fuse()`). The end-to-end budget (which includes MediaPipe landmark detection at 10–20 ms) is not measured end-to-end in a saved report. The claim is not fabricated but is scoped narrowly; the report should clarify what "< 1 ms" covers to avoid implying the full pipeline runs in < 1 ms.

---

### Q3 — Mini project report accuracy

#### 3a. CNN-LSTM claim is inaccurate

**`docs/ARCHITECTURE.md` block diagram:** Labels the fusion model as "CNN-LSTM Classifier".  
**`mini_project_report.md` Section 3.2:** "A trained TFLite model evaluates the fused scores."  
**`docs/report/mini_project_report.md` Section 4:** "… opt-in Node.js telemetry fleet backend."

**Actual model (`05_model_training/train_pipeline.py`):**
```python
def build_classification_model(input_dim: int, num_classes: int):
    model = tf.keras.Sequential([
        tf.keras.layers.Dense(16, activation='relu', input_shape=(input_dim,)),
        tf.keras.layers.Dense(16, activation='relu'),
        tf.keras.layers.Dense(num_classes, activation='softmax')
    ])
```

The trained fusion model is a two-layer Dense network (MLP), not a CNN-LSTM. The ARCHITECTURE.md block diagram label "CNN-LSTM Classifier" is incorrect and misleads readers about the architecture. The mini project report Section 3.2 avoids that specific claim but references ref [20] ("CNN-LSTM and Attention-Based Fusion") in a way that implies the same architecture is used here.

**Recommendation:** Correct the ARCHITECTURE.md label to "Dense MLP Classifier (TFLite)" and add a note in the mini project report that the production target is CNN-LSTM (per ref [20]) but the current trained model is a lightweight Dense MLP for edge deployment.

---

#### 3b. "Dlib-based 68-point facial landmark detection" in mini report

**`mini_project_report.md` Section 3.1:**
> "MediaPipe and Dlib-based 68-point facial landmarks map eye closure (EAR), mouth opening (MAR), yawning frequency, and PERCLOS."

**Actual default:** `01_behavioral_vision/landmarks/detector.py` defaults to `MediaPipeLandmarkDetector` (478-point). Dlib is an optional backend requiring a separate `.dat` file download. The system runs entirely on MediaPipe by default; Dlib is never used unless `behavioral.landmark_backend: "dlib"` is set in `config/default.yaml`.

**Recommendation:** Change "MediaPipe and Dlib-based 68-point" to "MediaPipe 478-point (Tasks API), with optional Dlib 68-point backend".

---

#### 3c. "Node.js telemetry fleet backend" claim

**`mini_project_report.md` Section 4:**
> "… and an opt-in Node.js telemetry fleet backend."

**Actual:** `04_hmi_alerts_fleet/fleet/telemetry_publisher.py` is a pure Python module using `paho-mqtt`. There is no Node.js code anywhere in the repository. The fleet backend publishes to a local MQTT broker; AWS IoT Core is a config flag (`aws_iot_enabled`), not a deployed service.

**Recommendation:** Remove "Node.js" from the report and replace with "Python MQTT publisher (paho-mqtt), with optional AWS IoT Core forwarding".

---

#### 3d. Sections that are correct

- Three-tier intervention protocol (Section 3.3) accurately describes the implementation.
- Multi-modal fusion and attention-based re-weighting on camera quality (Section 3.2) accurately describes `engine.py`.
- The timing table in Section 2.1 (1.0 s eyelid droop → Tier 2, 2.0 s → Tier 3) matches `config/thresholds.yaml`.
- Privacy claims (local processing, no raw biometrics) are implemented in `privacy/guard.py` and `config/privacy.yaml`.
- All reported system metrics carry a "SYNTHETIC" disclaimer.

---

### Q4 — References and citations

#### 4a. Synopsis has 21 references; mini report has 11

The synopsis `References` section lists 21 entries ([1]–[21]). The mini project report lists 11 (refs [1], [2], [4], [5], [6], [10], [11], [12], [13], [15], [16]). Missing from the report: [3], [7], [8], [9], [14], [17], [18], [19], [20], [21].

Of these, refs [3] (EEG system), [14] (DriCare face tracking), [16] (eye-blink deep learning) are directly relevant to the implemented behavioral pathway and arguably should appear if claims they support appear in the text. The report cites ref [16] in the reference list but refs [3], [14], [17] are discussed in the synopsis and not in the report.

**Status:** Acceptable for a condensed mini report. No fabricated citations.

#### 4b. Refs [2] and [7] — unconfirmed authors

**Synopsis:** Correctly flags both as "[Author(s) not confirmed] … [Verify authors/journal before final submission.]"  
**`docs/DECISIONS.md` (Decision 11):** Logs the issue.  
**Mini project report (Section 2.1):** Contains the flag sentence "References [2] and [7] have unconfirmed authors (verify before submission)."  
**Mini project report Reference list:** Lists [2] without the author warning.

**Recommendation:** Add the unconfirmed-author note to the reference list entry for [2] in the mini project report to be consistent with the synopsis.

#### 4c. DECISIONS.md note about refs [17]–[21] not matching Table 1

`docs/DECISIONS.md` (Decision 4) notes: "Table 1 rows [17]-[21] don't perfectly match the reference descriptions." This is a synopsis-internal inconsistency (the table description vs. the bibliographic entry). It has no effect on the implementation but should be verified before final submission.

---

### Q5 — Algorithms, datasets, or techniques mentioned in synopsis but absent from code

| Synopsis claim | Present in code? | Notes |
|---|---|---|
| EAR, PERCLOS, MAR, gaze deviation, head pose | ✅ Yes | `01_behavioral_vision/features/` |
| Approximate entropy on SWA | ✅ Yes | `vehicle/steering_analysis.py` line 30 |
| Dynamic Time Warping (DTW) | ✅ Yes | `vehicle/steering_analysis.py` line 115 |
| Lane offset / departure tracking | ✅ Yes | `vehicle/lane_analysis.py` |
| EEG θ/α ratio, ECG HRV (RMSSD, LF/HF) | ✅ Yes (synthetic) | `physiological/physio_sim.py` |
| Dynamic attention-weighted fusion | ✅ Yes | `fusion/engine.py` line 231 |
| Three-tier escalation | ✅ Yes | `intervention/state_machine.py` |
| PrivacyGuard / local-only processing | ✅ Yes | `privacy/guard.py` |
| TFLite model inference | ✅ Yes | `05_model_training/inference.py`, called from `fusion/engine.py` |
| CNN-LSTM model architecture | ❌ No | Fusion model is Dense MLP; CNN-LSTM is in refs but not built |
| Vision Transformer (ViT-B/16) | ❌ No | Only cited from ref [1]; not implemented |
| YOLOv8 / YOLOv10 | ❌ No | Only cited from refs [4] and [2]; not implemented |
| F-LSNN (Fuzzy Logic + LSTM) | ❌ No | Only cited from ref [2]; not implemented |
| EEG TinyML neural network (behind-ear) | ❌ No | Only cited from ref [17]; the physio path is a simulator |
| CAN Bus adaptive thresholds | ❌ No | CAN Bus is fully simulated; no real CAN adapter |
| Qt/QML HMI at 60+ FPS | ❌ No | Python actuator simulator only |
| Lottie JSON alert animations | ❌ No | No Lottie files exist |
| WebGL rendering | ❌ No | No WebGL code |
| Yocto Embedded Linux | ❌ No | Development/simulation environment only |
| ROS 2 middleware | ❌ No | ZMQ abstraction layer substitutes |

The ViT, YOLO, F-LSNN, and TinyML entries are cited algorithms from the literature review; the synopsis describes them as validation of the multi-modal approach, not as components built in this project. The gap is in the HMI rendering stack (Qt/QML, Lottie, WebGL) and the CNN-LSTM model, which the synopsis describes as part of "this system" rather than cited prior work.

---

### Q6 — Synopsis items that need updating to reflect what was actually built

The following synopsis claims either overstate the implemented system or need clarification before academic submission:

| Section | Synopsis statement | What to update |
|---|---|---|
| Section 7 (Alert UI) | "HMI developed using C++, Qt/QML, and WebGL, rendering at 60+ FPS … Lottie JSON files" | Clarify this is the production deployment target; the academic prototype uses a Python actuator simulator |
| Section 6 (Edge Processing) | "custom Yocto-based Embedded Linux distribution, with ROS 2 serving as middleware" | Note ROS 2 is replaced by ZMQ for development; Yocto is the deployment target |
| Section 4, Para 4 (Physiological) | "Multimodal CNN-LSTM architectures … serve as the reference model for the physiological fusion layer" | The implemented fusion model is a Dense MLP TFLite; CNN-LSTM is a design target, not what is currently trained |
| Section 4, Para 2 (Behavioural) | "Dlib-based 68-point facial landmark detection" | Dlib is an optional backend; the default is MediaPipe 478-point Tasks API |
| Feature list (Page 14) | "PERCOLAS" (typo for PERCLOS) | Fix typo — documented in `docs/DECISIONS.md` Decision 1 |

---

## Conclusions and Recommendations

### Critical fixes (affect academic integrity)

1. **Correct metrics in `mini_project_report.md` Section 5.3.** The numbers quoted (Behavioral MAE 0.0874, Vehicle MAE 0.0953, Fusion 95.30%) match no current report file. Replace with held-out evaluation numbers: Behavioral MAE 0.0863, Vehicle MAE 0.0954, Fusion Accuracy 94.10% (from `reports/evaluation_report.md`), labelled as synthetic-data-trained.

2. **Remove "CNN-LSTM" from `docs/ARCHITECTURE.md` block diagram.** The trained model is a Dense MLP. CNN-LSTM appears only in the referenced literature. Mislabelling it in a formal diagram creates a false technical claim.

3. **Remove "Node.js" from `mini_project_report.md` Section 4.** The fleet backend is Python/paho-mqtt.

### Moderate fixes (affect clarity or completeness)

4. **Update the HMI description** in both the mini report and synopsis to make clear that Qt/QML/WebGL is the production deployment target and the prototype uses a Python actuator simulator. Add a DECISIONS.md entry for this deviation.

5. **Correct the Dlib claim** in `mini_project_report.md` Section 3.1 to state MediaPipe 478-point as the default, with Dlib as an optional backend.

6. **Add unconfirmed-author warning to ref [2] in the mini report's reference list**, not just in Section 2.1.

7. **Enable `black` in `scripts/lint.sh`.** The line `# black --check .` is commented out. Per AGENTS.md Rule 3, code must be `black` clean; the check should run in CI. Log the activation in DECISIONS.md (or close Decision 13).

### Minor / informational

8. The latency claim "< 1 ms" in `mini_project_report.md` Section 5.2 is only for the fusion engine step. Clarify it covers only `engine.fuse()`, not the full pipeline (which is targeted at < 100 ms and budgeted at < 81 ms in ARCHITECTURE.md).

9. The synopsis (Section 2 header) says "sixteen recent research papers were reviewed" but lists 21 references. The discrepancy is noted in `docs/DECISIONS.md` Decision 4 and should be resolved in the synopsis before final submission.

10. The synopsis feature list (Page 14) spells PERCLOS as "PERCOLAS" — the typo is flagged in DECISIONS.md but should be corrected in the synopsis itself.

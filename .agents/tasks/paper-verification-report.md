# Paper Verification Report
**Cross-check: IEEE paper claims vs. actual codebase**
Verified: all files read directly from `/Users/apple/Documents/drowsy-detection`

---

## Summary

The vast majority of threshold and architecture claims are accurately reflected in the code. Five discrepancies were found:

| # | Paper Claim | Actual Value | Verdict |
|---|-------------|-------------|---------|
| 1 | 81 tests (24+21+23+13) | **86 tests** (28+4+21+28+9 = **not** 24+21+23+13) | **MISMATCH** — count and breakdown both wrong |
| 2 | Degraded weights: (0.60→0.06, 0.40→0.94) | 0.06 / 0.94 ✓ but only when `q_c < 0.20`, not at any hard threshold labelled "q_c" | Functionally correct; the trigger condition description in the abstract is accurate |
| 3 | Micro-correction threshold: **< 3 degrees** | `min_delta_deg = 1.0` degrees (range 1–8°); **not** a 3° hard threshold | **MISMATCH** |
| 4 | p95 latency < 70 ms (measured) | **No stored measurement** — benchmark script generates output at run-time; no archived run exists in the repo | **UNCONFIRMED** — claim cannot be verified without running the benchmark |
| 5 | `weights.yaml` degraded mode: 0.10/0.90 | Paper states 0.06/0.94; `weights.yaml` `degraded_behavior` block shows 0.10/0.90; engine.py computes 0.06/0.94 at runtime | **INCONSISTENCY** — YAML and engine disagree; paper matches engine, not YAML |

Everything else checked matches precisely.

---

## Evidence

### Q1 — Test count

**Paper claims: 81 tests (24 behavioral, 21 vehicle/physio, 23 fusion/state-machine, 13 HMI/alert)**

Actual counts from `def test_` occurrences in all five project test files (excluding virtual environment):

| File | Actual count | Paper category |
|------|-------------|----------------|
| `01_behavioral_vision/tests/test_features.py` | **24** | behavioral |
| `01_behavioral_vision/tests/test_overlay.py` | **4** | behavioral (not in paper breakdown) |
| `02_vehicle_physiological/tests/test_vehicle.py` | **21** | vehicle/physio |
| `03_fusion_edge_platform/tests/test_fusion.py` | **28** | fusion/state-machine |
| `04_hmi_alerts_fleet/tests/test_alerts.py` | **9** | HMI/alert |
| **TOTAL** | **86** | |

The paper's total (81) is wrong in two ways:
- `test_overlay.py` is a real project test file containing 4 tests not counted in the paper.
- The fusion file contains 28 tests, not 23 (it covers `TestFusionEngine`, `TestFusionFalsePositive`, `TestInterventionStateMachine`, and `TestPrivacyGuard` — 8 privacy guard tests are uncounted in the paper).
- `test_alerts.py` has 9 tests, not 13.
- Behavioral correctly shows 24 (`test_features.py` only) but the additional 4 overlay tests are absent from the stated breakdown.

Corrected breakdown: 28 behavioral (24+4), 21 vehicle, 28 fusion/state-machine, 9 HMI = **86 total**.

---

### Q2 — Config thresholds (`config/thresholds.yaml`)

All paper-stated thresholds match exactly:

| Paper claim | Config key | Actual value |
|-------------|-----------|-------------|
| PERCLOS mild 0.15 | `behavioral.perclos_threshold_mild` | **0.15** ✓ |
| PERCLOS moderate 0.30 | `behavioral.perclos_threshold_mod` | **0.30** ✓ |
| PERCLOS critical 0.50 | `behavioral.perclos_threshold_crit` | **0.50** ✓ |
| Calibration T_cal = 30 s | `behavioral.ear_baseline_calibration_s` | **30** ✓ |
| EAR drowsy ratio < 0.70 × baseline | `behavioral.ear_drowsy_ratio` | **0.7** ✓ |
| EAR absolute < 0.25 | `behavioral.ear_threshold_alert` | **0.25** ✓ |
| MAR > 0.50 | `behavioral.mar_threshold_yawn` | **0.50** ✓ |
| Yawn sustained ≥ 1.0 s | `behavioral.yawn_duration_min_s` | **1.0** ✓ |
| ≥ 3 yawns / 60 s | `behavioral.yawn_count_alert` / `yawn_count_window_s` | **3 / 60** ✓ |
| Eye closure critical > 2.0 s | `behavioral.blink_duration_crit_ms` | **2000** ✓ |
| Tier S_f ≥ 0.20 (T1) | `fusion.mild_threshold` | **0.20** ✓ |
| Tier S_f ≥ 0.40 (T2) | `fusion.moderate_threshold` | **0.40** ✓ |
| Tier S_f ≥ 0.65 (T3) | `fusion.critical_threshold` | **0.65** ✓ |
| Dwell 0.5 s (T1/T2) | `intervention.min_dwell_time_s` | **0.5** ✓ |
| Hysteresis 1.0 s | `intervention.hysteresis_s` | **1.0** ✓ |
| Cooldown 15.0 s | `intervention.cooldown_s` | **15.0** ✓ |
| Lane weaving index capped 0.30 | `vehicle.lane_weaving_index_max` | **0.3** ✓ |
| Micro-correction < 10/min = drowsy | `vehicle.micro_correction_rate_min` | **10** ✓ |

---

### Q3 — Fusion weights (`config/weights.yaml` and `engine.py`)

**Baseline weights (normal operation):**
- `config/weights.yaml` baseline: `behavior: 0.60`, `vehicle: 0.40` ✓
- `engine.py` default (`_base_w`): `{"behavior": 0.60, "vehicle": 0.40, "physio": 0.00}` ✓

**Degraded weights (camera blinded, `b_qual < 0.20`):**
- Paper claims: behavior → 0.06, vehicle → 0.94
- `engine.py` `_dynamic_weights()` computes:
  - `vehicle_boost = w["behavior"] * 0.90` → 0.60 × 0.90 = 0.54
  - `w["behavior"] = w["behavior"] * 0.10` → 0.60 × 0.10 = 0.06
  - `w["vehicle"] += vehicle_boost` → 0.40 + 0.54 = 0.94
  - After normalization (sum = 1.0): behavior = **0.06**, vehicle = **0.94** ✓

**INCONSISTENCY:** `config/weights.yaml` has a `degraded_behavior` block with `behavior: 0.10, vehicle: 0.90`. This block is **never loaded** by `engine.py` — the engine always computes degraded weights dynamically in `_dynamic_weights()`. The YAML block is dead configuration that contradicts both the paper and the live code. The paper's stated values (0.06 / 0.94) match only the engine computation, not the YAML.

---

### Q4 — State machine (tier thresholds, dwell, cooldown)

`03_fusion_edge_platform/intervention/state_machine.py`:

| Paper claim | Code | Match |
|-------------|------|-------|
| Dwell 0.5 s for T1/T2 | `min_dwell_time_s: float = 0.5` (default) | ✓ |
| Dwell 0 s for T3 | Tier 3 bypasses dwell: `if desired_tier == 3: self._current_tier = 3` immediately | ✓ |
| De-escalation 1.0 s hysteresis | `intervention.hysteresis_s: 1.0` in thresholds.yaml; `state_machine.py` default is `min_dwell_time_s=0.5` loaded from config | Note: the YAML key is `hysteresis_s` (1.0) but the code parameter is `min_dwell_time_s` (0.5); dwell and hysteresis are conflated. Both values are present — 0.5 is the dwell, 1.0 is in YAML as `hysteresis_s` but is not independently enforced in code. |
| Cooldown 15.0 s | `cooldown_s: float = 15.0` | ✓ |
| Eye closure critical override > 2.0 s | `blink_duration_crit_ms: 2000` triggers `MICRO_SLEEP_2S` → `LEVEL_CRITICAL` → Tier 3 bypass dwell | ✓ |

---

### Q5 — Training samples: 5,000 per modality

`05_model_training/train_pipeline.py`, function `generate_synthetic_data(num_samples: int = 5000)`:
- Behavioral: `size=(num_samples//2, 5)` alert + `size=(num_samples//2, 5)` drowsy → **5000 total** ✓
- Vehicle: same pattern → **5000 total** ✓
- Fusion: `size=(num_samples, 1)` → **5000 total** ✓

Paper claim matches exactly.

---

### Q6 — Feature dimensions

`05_model_training/train_pipeline.py` and `05_model_training/evaluate.py`:

| Paper claim | Code | Match |
|-------------|------|-------|
| Behavioral regressor: 5 features | `input_dim=5`, features `[EAR, PERCLOS, MAR, HeadPitch, HeadYaw]` | ✓ |
| Vehicle regressor: 3 features | `input_dim=3`, features `[SteeringApEn, LaneWeaving, MicroCorrectionRate]` | ✓ |
| Fusion classifier: 3 features, 4 classes | `input_dim=3`, `num_classes=4`, features `[BehavScore, VehicScore, PhysioScore]` | ✓ |

Also confirmed in `01_behavioral_vision/features/pipeline.py` `_compute_behavior_score()`: when calling the TFLite model, `features = [ear, perclos, mar, pitch, yaw]` (5 features).  
In `03_fusion_edge_platform/fusion/engine.py`: `features = [b_score, v_score, p_score]` (3 features).

---

### Q7 — p95 latency < 70 ms

`03_fusion_edge_platform/profiling/benchmark.py` runs 100 fusion-only iterations (no behavioral vision pipeline included) and writes a markdown report to `reports/evaluation_report.md`.

**Problem:** The benchmark only measures the **fusion engine step**, not end-to-end latency. End-to-end would include landmark detection, feature extraction, and all three pipeline stages. The script's report template states the budget is 100 ms, not 70 ms, and reads: `"Status": PASS` unconditionally.

**More critically:** No archived latency run exists in the repository. `reports/evaluation_report.md` contains **only model accuracy metrics** (MAE / accuracy) — it does not contain any `p95` latency figure. This report was generated by `05_model_training/evaluate.py`, which does not call the benchmark.

The benchmark (`profiling/benchmark.py`) was apparently never run and its output was never committed. The paper's stated p95 < 70 ms is **unverified** — there is no stored measurement to cite.

Additionally, the benchmark's internal claim ("Status: PASS") is set unconditionally in a format string, not conditionally on whether the measured p95 is actually under any target. It would print PASS regardless of the measured value.

---

### Q8 — Other claims

**478 facial landmarks:**  
`01_behavioral_vision/landmarks/detector.py` `MediaPipeLandmarkDetector` docstring: "478-point Face Mesh via MediaPipe Tasks API". `MockLandmarkDetector.detect()` generates `pts = np.full((478, 3), ...)`. ✓

**Camera at 30 FPS:**  
`config/default.yaml` `behavioral.fps_target: 30` ✓

**Micro-correction threshold: < 3 degrees (MISMATCH):**  
Paper states: "micro-correction threshold: < 3 degrees, flag if < 10 corrections/min".  
`02_vehicle_physiological/vehicle/steering_analysis.py` `micro_correction_rate()`: `min_delta_deg: float = 1.0`, `max_delta_deg: float = 8.0`. The range qualifying as a micro-correction is **1–8 degrees**, not "< 3 degrees". There is no 3° threshold anywhere in the codebase. The "< 10 corrections/min" rate threshold is correct (config: `micro_correction_rate_min: 10`), but the amplitude characterization in the paper is wrong.

**ZeroMQ publish-subscribe middleware:**  
`config/default.yaml` `system.middleware: "zmq"` ✓ (Paper claims ZeroMQ pub-sub bus.)

**Dwell time 0 s for Tier 3:**  
State machine code: `if desired_tier == 3: self._current_tier = 3` — no dwell check. ✓

**EAR < 0.70 × baseline OR < 0.25:**  
`ear.py` `BlinkDetector._threshold` returns `self.baseline_ear * self.ear_threshold_ratio` (default ratio 0.70). `config/thresholds.yaml` `ear_threshold_alert: 0.25` is used as the absolute floor. `engine.py` `_time_based_overrides` reads `ear_closed = ear < float(rules["ear_closed"])` (0.25). Both conditions are present in code. ✓

---

## Conclusions

### Verified matches
- All PERCLOS thresholds (0.15, 0.30, 0.50)
- EAR thresholds (0.70× baseline, 0.25 absolute)
- MAR yawn threshold (0.50), duration (1.0 s), count window (3/60 s)
- Calibration period (30 s)
- Tier score thresholds (0.20, 0.40, 0.65)
- Dwell time (0.5 s T1/T2, bypass for T3), cooldown (15.0 s)
- Eye-closure critical override (2.0 s)
- Fusion baseline weights (0.60/0.40)
- Degraded fusion weights — engine computes (0.06/0.94) matching the paper
- 5,000 synthetic training samples per modality
- Feature dimensions (5-feature behavioral, 3-feature vehicle, 3-feature 4-class fusion)
- 478 MediaPipe landmarks
- 30 FPS camera target
- Micro-correction rate threshold (< 10/min)
- Lane weaving cap (0.30)

### Mismatches and issues

**MISMATCH 1 — Test count (Q1):**  
Paper states 81 tests (24+21+23+13). Actual: **86 tests** (28+21+28+9 across four files, plus 4 overlay tests uncounted). The fusion/state-machine file has 28 tests (not 23), the HMI file has 9 tests (not 13), and 4 overlay tests exist but are absent from the stated breakdown.

**MISMATCH 2 — Micro-correction amplitude threshold (Q8):**  
Paper states "< 3 degrees" characterizes a micro-correction. Code uses range **1–8 degrees** (`min_delta_deg=1.0`, `max_delta_deg=8.0`). No 3° value exists anywhere in the codebase.

**INCONSISTENCY — `weights.yaml` degraded block:**  
`config/weights.yaml` `degraded_behavior` shows `behavior: 0.10, vehicle: 0.90`. This block is never read by the engine; the engine computes 0.06/0.94 dynamically. The YAML block is misleading dead configuration. Fix: update YAML to 0.06/0.94 or remove the block and add a comment referencing the engine computation.

**UNVERIFIED — p95 latency < 70 ms (Q7):**  
No stored benchmark run exists. `reports/evaluation_report.md` contains only model accuracy, not latency. The benchmark script measures only the fusion step (not full pipeline), and always prints "PASS" unconditionally. The paper's < 70 ms p95 claim cannot be verified from the repository as-is.

---

## Recommendations (do not implement — report only)

1. **Fix test count in paper**: Update to 86 total (28 behavioral including overlay, 21 vehicle, 28 fusion/state-machine, 9 HMI) — or if only `test_features.py` is intended as the "behavioral" count, acknowledge the overlay tests separately.

2. **Fix micro-correction amplitude description in paper**: The code defines a micro-correction as a steering reversal in the **1–8 degree** range, not "< 3 degrees". The paper should state "1–8 degree amplitude reversals" or align the code to 3° if that is the intended specification.

3. **Remove or correct `weights.yaml` `degraded_behavior` block**: It shows 0.10/0.90 but the runtime behavior is 0.06/0.94. Add a comment that actual degraded weights are computed dynamically in `fusion/engine.py _dynamic_weights()`.

4. **Run and archive the benchmark before submission**: Execute `python 03_fusion_edge_platform/profiling/benchmark.py` from the repo, commit the resulting report, and verify the p95 figure is actually < 70 ms. The current benchmark only times the fusion step — full pipeline latency (including landmark detection) must also be measured to support the end-to-end claim. The unconditional "PASS" in the benchmark output template should be replaced with a conditional check against the stated 70 ms target.

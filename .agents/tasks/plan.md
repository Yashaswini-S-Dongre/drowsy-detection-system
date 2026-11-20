# Implementation Plan
## Driver Drowsiness Detection System — Completion Work

**Project root:** `/Users/apple/Documents/drowsy-detection`
**Venv:** `./drowsy_env` (exists; activate with `source ./drowsy_env/bin/activate` on macOS/Linux, `.\drowsy_env\Scripts\Activate.ps1` on Windows)
**Test command:** `pytest` (config in `pytest.ini`; testpaths cover all four modules)
**Linting:** `ruff` + `black` (per AGENTS.md)

---

### Pre-implementation notes from codebase reading

1. **`inference.py` path is correct — no fix needed.**  
   `train_pipeline.py` writes models to `ROOT_DIR / "models"` where `ROOT_DIR = Path(__file__).resolve().parent` = `05_model_training/`. `inference.py` reads from `ROOT / "05_model_training" / "models"` where `ROOT = Path(__file__).resolve().parents[1]` = project root. Both resolve to `<project_root>/05_model_training/models/`. They match. Item 2 is a verification-only task.

2. **`LaneAnalyser` does not read from config** — `main.py` instantiates `LaneAnalyser(fps=fps)` using the hardcoded default `window_s=30.0`. The config key `lane_departure_window_s` (in `thresholds.yaml`) is never passed in. This must be fixed in `vehicle/main.py` so it reads `lane_departure_window_s` from config.

3. **`scripts/` already has** `run_all.sh`, `run_all.ps1`, `run_demo.sh`, `run_demo.ps1`. Missing scripts: `run_behavioral.sh/.ps1`, `run_vehicle.sh/.ps1`, `run_fusion.sh/.ps1`, `train_models.sh/.ps1`.

4. **`docs/DECISIONS.md` exists** with partial content (hardware abstraction, middleware, etc.). It needs the six required entries added/expanded per the task specification.

5. **`04_hmi_alerts_fleet/fleet/` does not exist** — must be created with `__init__.py` and `telemetry_publisher.py`.

6. **`04_hmi_alerts_fleet/design/tokens/` exists** but contains only a `.gitkeep`-style stub; `color_tokens.yaml` does not exist yet.

7. **`05_model_training/evaluate.py` does not exist** — must be created.

8. **`contracts/schemas/TelemetryEvent.json` confirms the schema** — fields: `ts`, `seq`, `vehicle_id`, `event_type`, `tier`, `duration_s`. No raw biometrics. The `telemetry_publisher.py` must emit only these fields.

9. **`config/privacy.yaml` uses key `telemetry.opt_in_default`** (not `telemetry_opt_in`). The publisher must check `telemetry.opt_in_default`.

---

- [ ] 1. Fix `config/thresholds.yaml` intervention section.
      Replace the four broken values (zeros and 200 kph) with realistic values per the task spec.  
      Files: `config/thresholds.yaml`  
      Change:
      - `hysteresis_s: 0.0` → `hysteresis_s: 2.0`
      - `min_dwell_time_s: 0.0` → `min_dwell_time_s: 3.0`
      - `cooldown_s: 0.0` → `cooldown_s: 15.0`
      - `recovery_speed_kph: 200.0` → `recovery_speed_kph: 5.0`  
      Verify: `python -c "import yaml; d=yaml.safe_load(open('config/thresholds.yaml')); i=d['intervention']; assert i['min_dwell_time_s']==3.0 and i['cooldown_s']==15.0 and i['recovery_speed_kph']==5.0 and i['hysteresis_s']==2.0, i"` — exits without error.

- [ ] 2. Verify `inference.py` ModelRegistry path (no code change needed).
      Confirm that `ROOT / "05_model_training" / "models"` (project root via `parents[1]`) matches where `train_pipeline.py` writes (`ROOT_DIR / "models"`, `ROOT_DIR` = `05_model_training/`). Both resolve to the same directory. Document the finding as a comment above the `model_path` line in `ModelRegistry.get_model()`.  
      Files: `05_model_training/inference.py` (comment only)  
      Verify: `python -c "from pathlib import Path; ROOT=Path('05_model_training/inference.py').resolve().parents[1]; p=ROOT/'05_model_training'/'models'/'behavioral.tflite'; print('path OK:', p)"` — prints the path without error.

- [ ] 3. Fix `LaneAnalyser` to read `lane_departure_window_s` from config.
      `vehicle/main.py` instantiates `LaneAnalyser(fps=fps)` using the default `window_s=30.0`. This means the config key `vehicle.lane_departure_window_s` (thresholds.yaml) is silently ignored. Fix `main.py` to load `thresholds.yaml` and pass `window_s=cfg['vehicle']['lane_departure_window_s']` when constructing `LaneAnalyser`. Also verify that `VehicleScorer` already reads `dtw_window_s` and `micro_correction_rate_min` from config (if not, fix similarly).  
      Files: `02_vehicle_physiological/vehicle/main.py`  
      Verify: `cd /Users/apple/Documents/drowsy-detection && pytest 02_vehicle_physiological/tests/ -v` — all existing tests pass. No new failures.

- [ ] 4. Add missing launch scripts to `scripts/`.
      Create six new scripts following the exact pattern of the existing `run_all.sh` and `run_all.ps1` (already in `scripts/`) — same venv detection logic, same `cd "$(dirname "$0")/.."` / `Set-Location -Path "$PSScriptRoot\.."` pattern.

      **`scripts/run_behavioral.sh`** (bash):
      ```
      #!/bin/bash
      set -e
      cd "$(dirname "$0")/.."
      # venv detection (same as run_all.sh)
      PYTHON=...
      $PYTHON -m 01_behavioral_vision.main --source webcam
      ```

      **`scripts/run_behavioral.ps1`** (PowerShell):
      ```
      Set-Location -Path "$PSScriptRoot\.."
      # venv detection
      & $python -m 01_behavioral_vision.main --source webcam
      ```

      **`scripts/run_vehicle.sh`** (bash):
      ```
      $PYTHON -m 02_vehicle_physiological.vehicle.main
      ```

      **`scripts/run_vehicle.ps1`** (PowerShell equivalent)

      **`scripts/run_fusion.sh`** (bash):
      ```
      $PYTHON -m 03_fusion_edge_platform.fusion.main
      ```
      (live mode — no `--demo` flag)

      **`scripts/run_fusion.ps1`** (PowerShell equivalent)

      **`scripts/train_models.sh`** (bash):
      ```
      #!/bin/bash
      set -e
      cd "$(dirname "$0")/.."
      source ./drowsy_env/bin/activate
      pip install --quiet tensorflow
      python 05_model_training/train_pipeline.py
      ```

      **`scripts/train_models.ps1`** (PowerShell):
      ```
      Set-Location -Path "$PSScriptRoot\.."
      .\drowsy_env\Scripts\Activate.ps1
      pip install --quiet tensorflow
      python 05_model_training\train_pipeline.py
      ```

      All .sh scripts must be executable (`chmod +x`).  
      Files: `scripts/run_behavioral.sh`, `scripts/run_behavioral.ps1`, `scripts/run_vehicle.sh`, `scripts/run_vehicle.ps1`, `scripts/run_fusion.sh`, `scripts/run_fusion.ps1`, `scripts/train_models.sh`, `scripts/train_models.ps1`  
      Verify: `bash -n scripts/run_behavioral.sh scripts/run_vehicle.sh scripts/run_fusion.sh scripts/train_models.sh` — syntax check exits 0. On Windows: `pwsh -NonInteractive -Command "Get-Command scripts\run_behavioral.ps1"` exits cleanly.

- [ ] 5. Expand `docs/DECISIONS.md` with the required entries.
      The file already exists with Sections 1–6. **Append** (do not replace) the following sections. Do not delete existing content. Add:

      **Section 7 — Synthetic Training Data (Privacy Constraint):**  
      The PRD states: "No raw biometric data shall be transmitted to external servers without explicit, opt-in consent." Real-world driver video and biometric datasets would require an IRB/ethics approval, driver consent forms, and anonymisation pipeline that is out of scope for this academic mini-project. The synthetic data generator in `train_pipeline.py` explicitly labels all outputs as `SYNTHETIC-DATA-TRAINED`. When a real annotated dataset (e.g., NTHU-DDD, UTA-RLDD) becomes available, it should replace the synthetic generator; the model architecture and TFLite export pipeline are dataset-agnostic.

      **Section 8 — MediaPipe Tasks API v1.x (not legacy `face_mesh`):**  
      MediaPipe's legacy `face_mesh` module (Solutions API) is deprecated in MediaPipe ≥ 0.10.x. The current codebase uses the Tasks API (`FaceLandmarker`) which is the supported path for future releases, provides better accuracy via the newer Blaze model, and returns landmarks with the same 468-point index set. This matches refs [14] and [16] which use landmark-based tracking.

      **Section 9 — ZMQ instead of ROS 2:**  
      ROS 2 is specified in the Design & Tech Stack document and synopsis (section 6). However, ROS 2 requires a full Ubuntu/Jetson development environment that is unavailable on macOS (the primary development machine per DECISIONS.md Section 6). The ZMQ middleware (`03_fusion_edge_platform/middleware/`) implements the same pub/sub topology with identical topic names from `contracts/topics.yaml`. When the system is deployed on Jetson with ROS 2, the bus module can be swapped to the `ros2` driver in `config/default.yaml` (`system.middleware: "ros2"`) without changing any publisher or subscriber code.

      **Section 10 — DTW reference templates are synthetic:**  
      The synopsis (section 3, Vehicle Behaviour Analysis) specifies Dynamic Time Warping against reference 'awake' and 'drowsy' templates from a real steering corpus. No such corpus is available for this mini-project. The `SteeringSimulator` generates parametrically controlled awake/drowsy SWA series that match the statistical profiles described in ref [5] (approximate entropy, micro-correction rate). Templates are clearly labelled synthetic in `steering_analysis.py`. When a real corpus (e.g., from CAN bus logging) becomes available, it should replace the simulator templates; the DTW function is data-agnostic.

      **Section 11 — Unconfirmed reference authors [2] and [7]:**  
      Per AGENTS.md rule 7: refs [2] and [7] in the synopsis have unconfirmed authors. Both are cited in the literature survey table and in the motivation section. The "verify before submission" flag is retained. Do not substitute other references or fabricate author names.

      **Section 12 — Lane analysis uses config-driven thresholds:**  
      `LaneAnalyser` reads `vehicle.lane_departure_window_s` from `config/thresholds.yaml` (passed via `vehicle/main.py`). `weaving_index_max` (`vehicle.lane_weaving_index_max`) is the upstream threshold applied in `03_fusion_edge_platform/fusion/engine.py` to classify lane weaving severity. Both values are config-driven with no hardcoded magic numbers in production code.

      Files: `docs/DECISIONS.md`  
      Verify: `grep -c "Section 1[012]" docs/DECISIONS.md` returns ≥ 3 (sections 10, 11, 12 present).

- [ ] 6. Create `04_hmi_alerts_fleet/fleet/` package with `telemetry_publisher.py`.
      Create the directory and files:

      **`04_hmi_alerts_fleet/fleet/__init__.py`** — empty init.

      **`04_hmi_alerts_fleet/fleet/telemetry_publisher.py`** — implement `TelemetryPublisher` class:

      - Constructor reads ALL config from YAML files at `config/` — no hardcoded values:
        - `config/default.yaml` → `fleet.mqtt_broker`, `fleet.mqtt_port`, `fleet.aws_iot_enabled`
        - `config/privacy.yaml` → `telemetry.opt_in_default` (this is the consent flag)
        - `contracts/topics.yaml` → subscribe topic `/drowsy/fusion`, publish topic `/drowsy/telemetry`
      - `start()` method: opens a ZMQ SUB socket subscribed to `/drowsy/fusion` (topic from contracts). If `telemetry.opt_in_default` is `False`, logs a message and returns immediately without publishing anything.
      - On each received fusion message (`FusionOutput` schema): extract `tier` (= `level`), `ts`, event duration (tracked from when level > 0 until level returns to 0). Build a `TelemetryEvent` dict with only `ts`, `seq`, `vehicle_id` (anonymised UUID loaded once at startup from a local identity file or generated fresh), `event_type` (`"drowsiness_event"` when tier > 0, `"recovery"` when tier returns to 0), `tier`, `duration_s`. NO raw EAR/MAR/PERCLOS/EEG/ECG.
      - If `fleet.aws_iot_enabled` is `False` (the default): publish via `paho-mqtt` to the local broker. If `paho-mqtt` is not installed, fall back to logging only (graceful degradation).
      - If `fleet.aws_iot_enabled` is `True`: stub that logs a "AWS IoT not configured in this build" warning and falls back to local MQTT.
      - All public methods have type hints and docstrings.
      - `vehicle_id` must be an anonymous UUID (not any real driver identifier) — generate with `uuid.uuid4()` at startup and write to a local state file (`config/.vehicle_id`) so it is stable across restarts but not meaningful PII.

      Files: `04_hmi_alerts_fleet/fleet/__init__.py`, `04_hmi_alerts_fleet/fleet/telemetry_publisher.py`  
      Verify: `python -c "from pathlib import Path; import sys; sys.path.insert(0, '.'); from 04_hmi_alerts_fleet.fleet.telemetry_publisher import TelemetryPublisher; print('import OK')"` — since Python identifiers can't start with digits, use: `python -c "import importlib.util; spec=importlib.util.spec_from_file_location('tp','04_hmi_alerts_fleet/fleet/telemetry_publisher.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print(m.TelemetryPublisher.__doc__)"` — prints the docstring without error. Also run `pytest 04_hmi_alerts_fleet/tests/ -v` (or add a smoke test if none exists).

- [ ] 7. Create `04_hmi_alerts_fleet/design/tokens/color_tokens.yaml`.
      The `04_hmi_alerts_fleet/design/tokens/` directory already exists. Create the YAML file with the exact color scheme from the Design & Tech Stack doc and PRD (Blue/Green monitoring, Amber Tier 1/2, Red Tier 3, dark background, Inter font):

      ```yaml
      # color_tokens.yaml
      # Automotive HMI colour design tokens
      # Source: Design & Tech Stack doc — "Color Psychology strictly applied"
      # Blue/Green for active/monitoring, Amber for Tier 1 & 2, Red for Tier 3

      monitoring:
        green: '#10b981'   # active / normal monitoring state
        blue:  '#3b82f6'   # system online indicator

      tier1_warning:
        amber: '#f59e0b'   # Tier 1 — early warning (yawns, minor drifts)

      tier2_warning:
        dark_amber: '#d97706'  # Tier 2 — moderate fatigue (eyelid drooping, erratic steering)

      tier3_critical:
        red: '#ef4444'    # Tier 3 — critical danger (micro-sleep, severe drift)

      background_dark: '#0a0a0a'   # dark UI during standard driving (zero distraction)

      font_primary: 'Inter'        # high-legibility sans-serif (2-second glanceability rule)
      ```

      Files: `04_hmi_alerts_fleet/design/tokens/color_tokens.yaml`  
      Verify: `python -c "import yaml; d=yaml.safe_load(open('04_hmi_alerts_fleet/design/tokens/color_tokens.yaml')); assert d['tier3_critical']['red']=='#ef4444' and d['font_primary']=='Inter', d"` — exits without error.

- [ ] 8. Create `05_model_training/evaluate.py`.
      Create an evaluation script that:

      - Has module-level docstring stating clearly: `SYNTHETIC-DATA-TRAINED — substitute real dataset when available`.
      - Imports `TFLiteRunner` and `ModelRegistry` from `inference.py` in the same directory.
      - Calls `generate_synthetic_data()` from `train_pipeline.py` with a fixed `random_seed=99` (different from training seed 42) to produce a held-out test split. Use the same feature schema.
      - For each of the three models (`behavioral`, `vehicle`, `fusion`):
        - Gets the runner via `ModelRegistry.get_model(name)`.
        - If `runner.is_available()` is `False`: prints `"[WARN] Model <name>.tflite not found — run train_models.sh first"` and skips gracefully.
        - If available: runs `runner.predict(features)` on each test sample in a loop, collects predictions vs. ground truth.
        - Behavioral and Vehicle: computes MAE from TFLite predictions vs. ground truth scores.
        - Fusion: computes accuracy (fraction of correct class predictions) from TFLite argmax vs. ground truth labels.
      - Ensures `reports/` directory exists.
      - Writes results to `reports/evaluation_report.md`:
        ```markdown
        # Evaluation Report
        > WARNING: SYNTHETIC-DATA-TRAINED — substitute real dataset when available.
        > All metrics are computed from actual TFLite inference calls, not fabricated.

        ## Behavioral Model
        * Test MAE: <value from actual inference>
        * Data: 1000 held-out synthetic samples (seed=99)

        ## Vehicle Model
        * Test MAE: <value from actual inference>
        ...

        ## Fusion Model
        * Test Accuracy: <value>%
        ...

        Generated: <ISO datetime>
        ```
      - All public functions have type hints and docstrings.
      - Runnable as `python 05_model_training/evaluate.py` from project root.

      Files: `05_model_training/evaluate.py`  
      Verify: `cd /Users/apple/Documents/drowsy-detection && python 05_model_training/evaluate.py` — if models exist it produces `reports/evaluation_report.md` with real metric values; if models are missing it prints instructive messages and exits 0 (no crash). Either way, exit code is 0.

- [ ] 9. Final lint and test pass.
      Run the full test suite and linters to confirm nothing is broken.  
      Commands:
      ```bash
      cd /Users/apple/Documents/drowsy-detection
      source ./drowsy_env/bin/activate
      ruff check 02_vehicle_physiological/ 04_hmi_alerts_fleet/ 05_model_training/ --select E,W,F
      pytest 02_vehicle_physiological/tests/ -v
      pytest 04_hmi_alerts_fleet/tests/ -v 2>/dev/null || true   # may be empty
      ```
      Fix any ruff/black violations introduced by the new files before considering done.  
      Files: Any file flagged by ruff.  
      Verify: `pytest 02_vehicle_physiological/tests/ -v` — all tests pass (exit 0). `ruff check` on new files — exit 0.

---

## Dependency order

Items must be implemented in this order (each depends on or must not break the previous):

1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9

- Item 3 (LaneAnalyser config fix) depends on item 1 (thresholds.yaml must have valid values first).
- Item 6 (telemetry_publisher) depends on `contracts/topics.yaml` (frozen, do not modify) and `config/privacy.yaml` (read-only).
- Item 8 (evaluate.py) depends on `inference.py` and `train_pipeline.py` being correct (items 2, 3 done).
- Item 9 (lint+test) must run last.

## Files to create (new)
- `scripts/run_behavioral.sh`
- `scripts/run_behavioral.ps1`
- `scripts/run_vehicle.sh`
- `scripts/run_vehicle.ps1`
- `scripts/run_fusion.sh`
- `scripts/run_fusion.ps1`
- `scripts/train_models.sh`
- `scripts/train_models.ps1`
- `04_hmi_alerts_fleet/fleet/__init__.py`
- `04_hmi_alerts_fleet/fleet/telemetry_publisher.py`
- `04_hmi_alerts_fleet/design/tokens/color_tokens.yaml`
- `05_model_training/evaluate.py`

## Files to modify (existing)
- `config/thresholds.yaml` — fix intervention section values
- `05_model_training/inference.py` — add path-correctness comment only
- `02_vehicle_physiological/vehicle/main.py` — pass `window_s` from config to `LaneAnalyser`
- `docs/DECISIONS.md` — append sections 7–12

## Files to never touch
- `contracts/` (frozen)
- `README.md` (already complete)
- Any already-complete module in `01_behavioral_vision/`, `03_fusion_edge_platform/`, `04_hmi_alerts_fleet/alert_outputs/`

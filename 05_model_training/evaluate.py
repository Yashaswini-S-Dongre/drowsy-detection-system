"""
05_model_training/evaluate.py
==============================
Held-out evaluation of the three TFLite models trained by train_pipeline.py.

.. warning::
    SYNTHETIC-DATA-TRAINED — All metrics in this script are computed on
    held-out *synthetic* test data (seed=99).  Substitute a real annotated
    dataset (e.g. NTHU-DDD, UTA-RLDD) when one becomes available.  The
    model architecture and TFLite inference pipeline are dataset-agnostic.

Usage::

    python 05_model_training/evaluate.py

If the ``.tflite`` models have not yet been built, run ``train_models.sh``
(or ``train_models.ps1`` on Windows) first.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

# ---------------------------------------------------------------------------
# Path setup — allow running from project root as:
#     python 05_model_training/evaluate.py
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_HERE))

# ---------------------------------------------------------------------------
# Imports from sibling modules
# ---------------------------------------------------------------------------
from inference import ModelRegistry, TFLiteRunner  # noqa: E402  (local import)

# Note: train_pipeline.py imports tensorflow at module level, which may not
# be installed in inference-only environments.  We therefore duplicate the
# held-out data generation logic below rather than importing from train_pipeline.


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def make_held_out_data(seed: int = 99, num_samples: int = 1000) -> dict:
    """Generate a held-out synthetic test split independent from training.

    Uses *seed=99* (training uses seed=42) to guarantee the test set does
    not overlap with training data.

    Parameters
    ----------
    seed:
        NumPy random seed.  Must differ from the training seed (42).
    num_samples:
        Number of test samples to generate per modality.

    Returns
    -------
    dict
        Keys ``"behavior"``, ``"vehicle"``, ``"fusion"`` each mapping to
        ``(X, y)`` ndarrays matching the feature shapes used in training.
    """
    # Temporarily override the seed inside generate_synthetic_data.
    # generate_synthetic_data always calls np.random.seed(42) internally,
    # so we regenerate directly here with the held-out seed.
    rng = np.random.default_rng(seed)

    n = num_samples
    half = n // 2

    # --- Behavioral (input_dim=5) ---
    X_b_alert = rng.normal(
        loc=[0.3, 0.05, 0.0, 0.0, 0.0],
        scale=[0.05, 0.02, 0.05, 0.05, 0.05],
        size=(half, 5),
    )
    y_b_alert = rng.uniform(0.0, 0.3, size=(half, 1))

    X_b_drowsy = rng.normal(
        loc=[0.15, 0.4, 0.8, 0.4, 0.2],
        scale=[0.08, 0.2, 0.2, 0.2, 0.2],
        size=(half, 5),
    )
    y_b_drowsy = rng.uniform(0.6, 1.0, size=(half, 1))

    X_behav = np.vstack([X_b_alert, X_b_drowsy])
    y_behav = np.vstack([y_b_alert, y_b_drowsy])

    # --- Vehicle (input_dim=3) ---
    X_v_alert = rng.normal(
        loc=[1.2, 0.05, 30.0],
        scale=[0.2, 0.02, 5.0],
        size=(half, 3),
    )
    y_v_alert = rng.uniform(0.0, 0.3, size=(half, 1))

    X_v_drowsy = rng.normal(
        loc=[0.5, 0.6, 5.0],
        scale=[0.3, 0.2, 3.0],
        size=(half, 3),
    )
    y_v_drowsy = rng.uniform(0.6, 1.0, size=(half, 1))

    X_vehic = np.vstack([X_v_alert, X_v_drowsy])
    y_vehic = np.vstack([y_v_alert, y_v_drowsy])

    # --- Fusion (input_dim=3, 4-class) ---
    X_fus = np.hstack([y_behav, y_vehic, rng.uniform(0, 1, size=(n, 1))])
    y_fus_list = []
    for row in X_fus:
        avg = float(np.mean(row))
        if avg < 0.3:
            y_fus_list.append(0)
        elif avg < 0.6:
            y_fus_list.append(1)
        elif avg < 0.8:
            y_fus_list.append(2)
        else:
            y_fus_list.append(3)
    y_fus = np.array(y_fus_list)

    return {
        "behavior": (X_behav, y_behav),
        "vehicle": (X_vehic, y_vehic),
        "fusion": (X_fus, y_fus),
    }


def evaluate_regression(
    runner: TFLiteRunner,
    X: np.ndarray,
    y: np.ndarray,
) -> float:
    """Run TFLite regression inference and return mean absolute error.

    Parameters
    ----------
    runner:
        Initialised :class:`TFLiteRunner` for a regression model.
    X:
        Input feature matrix of shape ``(n_samples, input_dim)``.
    y:
        Ground-truth labels of shape ``(n_samples, 1)`` or ``(n_samples,)``.

    Returns
    -------
    float
        Mean absolute error computed from actual TFLite inference calls.
    """
    y_flat = y.flatten()
    predictions = []
    for features in X:
        pred = runner.predict(features.tolist())
        if pred is None:
            raise RuntimeError("TFLiteRunner.predict returned None unexpectedly.")
        predictions.append(float(pred[0]))
    mae = float(np.mean(np.abs(np.array(predictions) - y_flat)))
    return mae


def evaluate_classification(
    runner: TFLiteRunner,
    X: np.ndarray,
    y: np.ndarray,
) -> float:
    """Run TFLite classification inference and return accuracy (0–1).

    Parameters
    ----------
    runner:
        Initialised :class:`TFLiteRunner` for a classification model.
    X:
        Input feature matrix of shape ``(n_samples, input_dim)``.
    y:
        Ground-truth class labels of shape ``(n_samples,)``.

    Returns
    -------
    float
        Fraction of correct predictions (accuracy in [0, 1]).
    """
    correct = 0
    for features, label in zip(X, y):
        pred = runner.predict(features.tolist())
        if pred is None:
            raise RuntimeError("TFLiteRunner.predict returned None unexpectedly.")
        predicted_class = int(np.argmax(pred))
        if predicted_class == int(label):
            correct += 1
    return correct / len(y)


def run_evaluation(reports_dir: Optional[Path] = None) -> None:
    """Evaluate all three TFLite models and write an evaluation report.

    If any model file is missing, a clear instruction is printed and that
    model is skipped gracefully (exit code remains 0).

    Parameters
    ----------
    reports_dir:
        Directory where ``evaluation_report.md`` will be written.
        Defaults to ``<project_root>/reports/``.
    """
    reports_dir = reports_dir or (_PROJECT_ROOT / "reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    data = make_held_out_data(seed=99, num_samples=1000)

    results: dict[str, str] = {}
    timestamp = datetime.now(tz=timezone.utc).isoformat()

    # -----------------------------------------------------------------------
    # Behavioral model (regression, input_dim=5)
    # -----------------------------------------------------------------------
    runner_b = ModelRegistry.get_model("behavioral")
    if not runner_b.is_available():
        print(
            "[WARN] Model behavioral.tflite not found — "
            "run train_models.sh first, then re-run evaluate.py."
        )
        results["behavioral"] = "MODEL NOT FOUND — run train_models.sh first."
    else:
        X_b, y_b = data["behavior"]
        mae_b = evaluate_regression(runner_b, X_b, y_b)
        results["behavioral"] = f"Test MAE: {mae_b:.4f}"
        print(f"[INFO] Behavioral — MAE={mae_b:.4f}")

    # -----------------------------------------------------------------------
    # Vehicle model (regression, input_dim=3)
    # -----------------------------------------------------------------------
    runner_v = ModelRegistry.get_model("vehicle")
    if not runner_v.is_available():
        print(
            "[WARN] Model vehicle.tflite not found — "
            "run train_models.sh first, then re-run evaluate.py."
        )
        results["vehicle"] = "MODEL NOT FOUND — run train_models.sh first."
    else:
        X_v, y_v = data["vehicle"]
        mae_v = evaluate_regression(runner_v, X_v, y_v)
        results["vehicle"] = f"Test MAE: {mae_v:.4f}"
        print(f"[INFO] Vehicle     — MAE={mae_v:.4f}")

    # -----------------------------------------------------------------------
    # Fusion model (classification, input_dim=3, 4 classes)
    # -----------------------------------------------------------------------
    runner_f = ModelRegistry.get_model("fusion")
    if not runner_f.is_available():
        print(
            "[WARN] Model fusion.tflite not found — "
            "run train_models.sh first, then re-run evaluate.py."
        )
        results["fusion"] = "MODEL NOT FOUND — run train_models.sh first."
    else:
        X_f, y_f = data["fusion"]
        acc_f = evaluate_classification(runner_f, X_f, y_f)
        results["fusion"] = f"Test Accuracy: {acc_f * 100:.2f}%"
        print(f"[INFO] Fusion      — Accuracy={acc_f * 100:.2f}%")

    # -----------------------------------------------------------------------
    # Write report
    # -----------------------------------------------------------------------
    report_path = reports_dir / "evaluation_report.md"
    report_lines = [
        "# Evaluation Report",
        "",
        "> **WARNING: SYNTHETIC-DATA-TRAINED** — All metrics are computed on "
        "held-out *synthetic* test data (seed=99, 1000 samples).  "
        "Substitute a real annotated dataset when available.",
        ">",
        "> All metrics come from actual TFLite inference calls — none are fabricated.",
        "",
        "## Behavioral Model",
        f"* {results.get('behavioral', 'N/A')}",
        "* Data: 1000 held-out synthetic samples (seed=99, input_dim=5)",
        "* Task: Regression → drowsiness score [0, 1]",
        "",
        "## Vehicle Model",
        f"* {results.get('vehicle', 'N/A')}",
        "* Data: 1000 held-out synthetic samples (seed=99, input_dim=3)",
        "* Task: Regression → drowsiness score [0, 1]",
        "",
        "## Fusion Model",
        f"* {results.get('fusion', 'N/A')}",
        "* Data: 1000 held-out synthetic samples (seed=99, input_dim=3)",
        "* Task: 4-class classification → alert level [0–3]",
        "",
        f"Generated: {timestamp}",
    ]
    report_path.write_text("\n".join(report_lines))
    print(f"[INFO] Evaluation report written to {report_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_evaluation()

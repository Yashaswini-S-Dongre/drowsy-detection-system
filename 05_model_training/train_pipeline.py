"""
05_model_training/train_pipeline.py
===================================
Generates synthetic data, trains neural networks, evaluates them,
outputs accuracy reports, and exports TFLite models for Edge inference.

Complies with the rule: "Never fabricate accuracy numbers. All reported
metrics must come from an actual run, saved in a report file. If a dataset
is unavailable, say so and use the synthetic path, clearly labelled as synthetic."
"""

import os
from pathlib import Path

import numpy as np
import tensorflow as tf

ROOT_DIR = Path(__file__).resolve().parent

def generate_synthetic_data(num_samples: int = 5000):
    """
    Generates synthetic datasets for Behavioral, Vehicle, and Fusion pathways.
    Features are simplified representations of the pipeline outputs.
    """
    np.random.seed(42)
    print("[INFO] Generating synthetic dataset...")

    # 1. Behavioral Data
    # Features: [EAR, PERCLOS, MAR, HeadPitch, HeadYaw]
    # Label: Score (0.0 to 1.0)
    X_behav_alert = np.random.normal(loc=[0.3, 0.05, 0.0, 0.0, 0.0], scale=[0.05, 0.02, 0.05, 0.05, 0.05], size=(num_samples//2, 5))
    y_behav_alert = np.random.uniform(0.0, 0.3, size=(num_samples//2, 1))

    X_behav_drowsy = np.random.normal(loc=[0.15, 0.4, 0.8, 0.4, 0.2], scale=[0.08, 0.2, 0.2, 0.2, 0.2], size=(num_samples//2, 5))
    y_behav_drowsy = np.random.uniform(0.6, 1.0, size=(num_samples//2, 1))

    X_behav = np.vstack([X_behav_alert, X_behav_drowsy])
    y_behav = np.vstack([y_behav_alert, y_behav_drowsy])

    # 2. Vehicle Data
    # Features: [SteeringApEn, LaneWeaving, MicroCorrectionRate]
    X_vehic_alert = np.random.normal(loc=[1.2, 0.05, 30.0], scale=[0.2, 0.02, 5.0], size=(num_samples//2, 3))
    y_vehic_alert = np.random.uniform(0.0, 0.3, size=(num_samples//2, 1))

    X_vehic_drowsy = np.random.normal(loc=[0.5, 0.6, 5.0], scale=[0.3, 0.2, 3.0], size=(num_samples//2, 3))
    y_vehic_drowsy = np.random.uniform(0.6, 1.0, size=(num_samples//2, 1))

    X_vehic = np.vstack([X_vehic_alert, X_vehic_drowsy])
    y_vehic = np.vstack([y_vehic_alert, y_vehic_drowsy])

    # 3. Fusion Data
    # Features: [BehavScore, VehicScore, PhysioScore]
    # Label: 4 levels [0, 1, 2, 3]
    X_fus = np.hstack([y_behav, y_vehic, np.random.uniform(0, 1, size=(num_samples, 1))])
    y_fus = []
    for row in X_fus:
        avg_score = np.mean(row)
        if avg_score < 0.3:
            y_fus.append(0)
        elif avg_score < 0.6:
            y_fus.append(1)
        elif avg_score < 0.8:
            y_fus.append(2)
        else:
            y_fus.append(3)
    y_fus = np.array(y_fus)

    # Shuffle
    indices = np.arange(num_samples)
    np.random.shuffle(indices)

    return {
        "behavior": (X_behav[indices], y_behav[indices]),
        "vehicle":  (X_vehic[indices], y_vehic[indices]),
        "fusion":   (X_fus[indices], y_fus[indices])
    }


def build_regression_model(input_dim: int):
    model = tf.keras.Sequential([
        tf.keras.layers.Dense(16, activation='relu', input_shape=(input_dim,)),
        tf.keras.layers.Dense(8, activation='relu'),
        tf.keras.layers.Dense(1, activation='sigmoid')
    ])
    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    return model


def build_classification_model(input_dim: int, num_classes: int):
    model = tf.keras.Sequential([
        tf.keras.layers.Dense(16, activation='relu', input_shape=(input_dim,)),
        tf.keras.layers.Dense(16, activation='relu'),
        tf.keras.layers.Dense(num_classes, activation='softmax')
    ])
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    return model


def export_to_tflite(model, output_path: Path):
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    tflite_model = converter.convert()
    with open(output_path, "wb") as f:
        f.write(tflite_model)
    print(f"[INFO] Exported {output_path.name} ({len(tflite_model)} bytes)")


def main():
    os.makedirs(ROOT_DIR / "models", exist_ok=True)
    os.makedirs(ROOT_DIR / "reports", exist_ok=True)

    data = generate_synthetic_data()

    report_lines = [
        "# Model Training & Evaluation Report",
        "> NOTE: Real datasets were unavailable (privacy restrictions). All training and metrics "
        "were generated using SYNTHETIC data designed to mimic real-world distributions.",
        ""
    ]

    # --- 1. Behavioral Model ---
    X, y = data["behavior"]
    split = int(0.8 * len(X))
    X_train, y_train = X[:split], y[:split]
    X_test, y_test = X[split:], y[split:]

    model_b = build_regression_model(input_dim=5)
    model_b.fit(X_train, y_train, epochs=10, batch_size=32, verbose=0)
    loss, mae = model_b.evaluate(X_test, y_test, verbose=0)

    export_to_tflite(model_b, ROOT_DIR / "models" / "behavioral.tflite")
    report_lines.append(f"## Behavioral Model\n* **Task:** Regression (Features -> Drowsiness Score)\n* **Test MAE:** {mae:.4f}\n* **Status:** Converted to TFLite\n")


    # --- 2. Vehicle Model ---
    X, y = data["vehicle"]
    X_train, y_train = X[:split], y[:split]
    X_test, y_test = X[split:], y[split:]

    model_v = build_regression_model(input_dim=3)
    model_v.fit(X_train, y_train, epochs=10, batch_size=32, verbose=0)
    loss, mae = model_v.evaluate(X_test, y_test, verbose=0)

    export_to_tflite(model_v, ROOT_DIR / "models" / "vehicle.tflite")
    report_lines.append(f"## Vehicle Model\n* **Task:** Regression (Features -> Drowsiness Score)\n* **Test MAE:** {mae:.4f}\n* **Status:** Converted to TFLite\n")


    # --- 3. Fusion Model ---
    X, y = data["fusion"]
    X_train, y_train = X[:split], y[:split]
    X_test, y_test = X[split:], y[split:]

    model_f = build_classification_model(input_dim=3, num_classes=4)
    model_f.fit(X_train, y_train, epochs=15, batch_size=32, verbose=0)
    loss, acc = model_f.evaluate(X_test, y_test, verbose=0)

    export_to_tflite(model_f, ROOT_DIR / "models" / "fusion.tflite")
    report_lines.append(f"## Fusion Model\n* **Task:** Classification (Sub-scores -> Alert Level [0-3])\n* **Test Accuracy:** {acc*100:.2f}%\n* **Status:** Converted to TFLite\n")

    # Write report
    report_path = ROOT_DIR / "reports" / "training_report.md"
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    print(f"[INFO] Report generated at {report_path.name}")


if __name__ == "__main__":
    main()

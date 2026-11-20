#!/usr/bin/env bash
# train_models.sh
# Train all TFLite models using the synthetic data pipeline.
# Installs tensorflow if not already present, then runs train_pipeline.py.
set -e

cd "$(dirname "$0")/.."

# TensorFlow requires Python 3.13 in this project's venv.
# Prefer python3.13 if available (has TF), fall back to python3.
if [ -f "./drowsy_env/bin/python3.13" ]; then
    PYTHON="./drowsy_env/bin/python3.13"
    PIP="./drowsy_env/bin/pip3.13"
elif [ -f "./drowsy_env/bin/python3" ]; then
    PYTHON="./drowsy_env/bin/python3"
    PIP="./drowsy_env/bin/pip3"
elif [ -f "./venv/bin/python" ]; then
    PYTHON="./venv/bin/python"
    PIP="./venv/bin/pip"
else
    PYTHON="python3"
    PIP="pip3"
fi

echo "Using Python: $($PYTHON --version) ($PYTHON)"
$PIP install --quiet tensorflow
$PYTHON 05_model_training/train_pipeline.py
echo "Training complete. Models saved to 05_model_training/models/"

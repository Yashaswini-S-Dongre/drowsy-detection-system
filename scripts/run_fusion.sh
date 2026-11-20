#!/usr/bin/env bash
# run_fusion.sh
# Launch the fusion engine in live mode (no --demo flag).
set -e

cd "$(dirname "$0")/.."

# Prefer virtual environment python if present
if [ -f "./drowsy_env/bin/python" ]; then
    PYTHON="./drowsy_env/bin/python"
elif [ -f "./venv/bin/python" ]; then
    PYTHON="./venv/bin/python"
else
    PYTHON="python3"
fi

echo "Using Python: $($PYTHON --version) ($PYTHON)"
$PYTHON -m 03_fusion_edge_platform.fusion.main "$@"

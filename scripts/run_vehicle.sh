#!/usr/bin/env bash
# run_vehicle.sh
# Launch the vehicle & physiological monitoring node.
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
$PYTHON -m 02_vehicle_physiological.vehicle.main "$@"

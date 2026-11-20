#!/bin/bash
# run_all.sh
# Starts all system components in multi-process pipeline mode

set -e
trap 'echo -e "\nShutting down all processes..."; kill -INT $(jobs -p) 2>/dev/null; sleep 1; exit' SIGINT SIGTERM EXIT

echo "Starting Driver Drowsiness Detection System..."

# Ensure we're in the project root
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

echo "1. Starting Middleware (ZMQ Broker)..."
$PYTHON -m 03_fusion_edge_platform.middleware.zmq_broker &
BROKER_PID=$!
sleep 0.5

echo "2. Starting HMI & Actuators..."
$PYTHON -m 04_hmi_alerts_fleet.hmi_qml.main &
sleep 0.3

echo "3. Starting Fusion Engine..."
$PYTHON -m 03_fusion_edge_platform.fusion.main &
sleep 0.3

echo "4. Starting Processing Nodes..."
$PYTHON -m 01_behavioral_vision.main --source webcam &
$PYTHON -m 02_vehicle_physiological.vehicle.main &

echo "=========================================================="
echo "All nodes running! Data is flowing through the bus."
echo "Press Ctrl+C to stop all components."
echo "=========================================================="

wait

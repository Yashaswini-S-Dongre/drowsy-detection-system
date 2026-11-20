#!/bin/bash
# test_all.sh
# Runs pytest on all modules

cd "$(dirname "$0")/.."

echo "Running tests across all modules..."
python3 -m pytest 01_behavioral_vision/tests
python3 -m pytest 02_vehicle_physiological/tests
python3 -m pytest 03_fusion_edge_platform/tests
python3 -m pytest 04_hmi_alerts_fleet/tests


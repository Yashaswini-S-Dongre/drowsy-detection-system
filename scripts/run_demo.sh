#!/bin/bash
# run_demo.sh
# Demonstrates the full 3-tier alert system with real audio + haptic output.
# Scenario: ALERT (awake) → Tier 1 (mild) → Tier 2 (moderate) → Tier 3 (critical) → recovery

set -e

echo ""
echo "=========================================================="
echo "  Driver Drowsiness Detection — 3-Tier Demo"
echo "  Visual | Auditory | Haptic alerts per tier"
echo "=========================================================="

cd "$(dirname "$0")/.."

if [ -f "./drowsy_env/bin/python" ]; then
    PYTHON="./drowsy_env/bin/python"
elif [ -f "./venv/bin/python" ]; then
    PYTHON="./venv/bin/python"
else
    PYTHON="python3"
fi

echo "Using: $($PYTHON --version) ($PYTHON)"
echo ""

# Demo runs for ~30 s: 4 s awake + 7 s × 3 phases + 5 s recovery
# The --speed-kph flag is the simulated vehicle speed (used for Tier-3 latch release)
$PYTHON -m 03_fusion_edge_platform.fusion.main --demo --speed-kph 60

"""
conftest.py — Project-level pytest configuration.
Ensures all module sub-packages are importable without installation.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Add every module root so `from vehicle.steering_analysis import ...` etc. works
for module_root in [
    ROOT / "01_behavioral_vision",
    ROOT / "02_vehicle_physiological",
    ROOT / "03_fusion_edge_platform",
    ROOT / "04_hmi_alerts_fleet",
]:
    if str(module_root) not in sys.path:
        sys.path.insert(0, str(module_root))

# Also add the project root itself
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

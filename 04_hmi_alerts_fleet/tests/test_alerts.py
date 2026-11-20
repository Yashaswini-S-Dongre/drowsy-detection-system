"""
tests/test_alerts.py
=====================
Unit tests for alert outputs: actuator simulator, post-trip summary reporter.
No hardware required. Run: pytest 04_hmi_alerts_fleet/tests/ -v
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "04_hmi_alerts_fleet"))

from alert_outputs.actuator_sim import ActuatorSimulator, TripSummaryReporter  # noqa: E402


def _tier3_cmd() -> dict:
    return json.load(open(ROOT / "contracts/sample_messages/alert_tier3.json"))


def _tier0_cmd() -> dict:
    return {
        "ts": 1000.0, "seq": 0, "timestamp": 1000.0, "tier": 0,
        "visual": {"color": "#0a0a0a", "message": "", "animation": "none"},
        "audio": {"type": "none", "volume": 0.0},
        "haptic": {"pattern": "none", "intensity": 0.0},
        "seatbelt_tighten": False, "hazard_lights": False,
        "emergency_stop_assist": False, "rest_break_prompt": False,
    }


class TestActuatorSimulator:
    def test_tier3_activates_all_actuators(self):
        sim   = ActuatorSimulator(verbose=False)
        event = sim.process_alert_command(_tier3_cmd())
        assert event.tier == 3
        assert event.hazard_lights        is True
        assert event.emergency_stop_assist is True
        assert event.seatbelt_tighten     is True
        assert event.audio_type           == "alarm_continuous"
        assert event.audio_volume         == 1.0
        assert event.haptic_pattern       == "continuous"

    def test_tier0_activates_nothing(self):
        sim   = ActuatorSimulator(verbose=False)
        event = sim.process_alert_command(_tier0_cmd())
        assert event.tier                  == 0
        assert event.hazard_lights         is False
        assert event.emergency_stop_assist is False
        assert event.seatbelt_tighten      is False
        assert event.audio_type            == "none"
        assert event.haptic_pattern        == "none"

    def test_event_log_accumulates(self):
        sim = ActuatorSimulator(verbose=False)
        sim.process_alert_command(_tier0_cmd())
        sim.process_alert_command(_tier3_cmd())
        assert len(sim.event_log) == 2

    def test_event_log_written_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "alerts.jsonl"
            sim      = ActuatorSimulator(log_path=log_path, verbose=False)
            sim.process_alert_command(_tier3_cmd())
            lines = log_path.read_text().strip().split("\n")
            assert len(lines) == 1
            record = json.loads(lines[0])
            assert record["tier"] == 3
            assert record["hazard"] is True
            assert record["esa"]   is True

    def test_event_log_contains_no_raw_biometrics(self):
        """Privacy: log must not store raw biometric values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "alerts.jsonl"
            sim      = ActuatorSimulator(log_path=log_path, verbose=False)
            sim.process_alert_command(_tier3_cmd())
            content = log_path.read_text()
            forbidden = ["ear_left", "perclos_60s", "mar", "hrv_rmssd", "theta_alpha"]
            for field in forbidden:
                assert field not in content, \
                    f"Raw biometric field '{field}' found in alert log — privacy violation"

    def test_active_tier_updates(self):
        sim = ActuatorSimulator(verbose=False)
        assert sim.active_tier == 0
        sim.process_alert_command(_tier3_cmd())
        assert sim.active_tier == 3
        sim.process_alert_command(_tier0_cmd())
        assert sim.active_tier == 0


class TestTripSummaryReporter:
    def _write_events(self, path: Path, events: list[dict]) -> None:
        with open(path, "w") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

    def test_summary_with_no_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "empty.jsonl"
            r    = TripSummaryReporter(path)
            s    = r.generate_summary()
            assert s["events"] == 0

    def test_summary_counts_tiers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path   = Path(tmpdir) / "log.jsonl"
            events = [
                {"ts_ms": 1000.0, "tier": 1, "seatbelt": False, "hazard": False,
                 "esa": False, "haptic": "none", "audio": "none", "message": ""},
                {"ts_ms": 2000.0, "tier": 2, "seatbelt": True,  "hazard": False,
                 "esa": False, "haptic": "none", "audio": "chime", "message": ""},
                {"ts_ms": 3000.0, "tier": 3, "seatbelt": True,  "hazard": True,
                 "esa": True, "haptic": "continuous", "audio": "alarm_continuous", "message": ""},
            ]
            self._write_events(path, events)
            r = TripSummaryReporter(path)
            s = r.generate_summary()
            assert s["tier1_alerts"] == 1
            assert s["tier2_alerts"] == 1
            assert s["tier3_alerts"] == 1
            assert s["total_alerts"] == 3
            assert "CRITICAL" in s["overall_alertness"]

    def test_summary_excellent_with_no_alerts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "log.jsonl"
            self._write_events(path, [])
            r = TripSummaryReporter(path)
            s = r.generate_summary()
            # Even empty file → no events summary
            assert s.get("events", 0) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

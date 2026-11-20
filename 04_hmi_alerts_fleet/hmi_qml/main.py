"""
04_hmi_alerts_fleet/hmi_qml/main.py
===================================
HMI node. Subscribes to /drowsy/alert and triggers ActuatorSimulator.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "04_hmi_alerts_fleet"))


def main():
    try:
        from _03_fusion_edge_platform.middleware.bus import Subscriber
    except ImportError:
        sys.path.insert(0, str(ROOT / "03_fusion_edge_platform"))
        from middleware.bus import Subscriber

    from alert_outputs.actuator_sim import ActuatorSimulator, TripSummaryReporter

    sub = Subscriber(topics=["/drowsy/alert"])
    log_file = ROOT / "reports" / "alerts_log.jsonl"
    if log_file.exists():
        log_file.unlink()

    sim = ActuatorSimulator(log_path=log_file, verbose=True)

    print("[hmi.main] HMI and Actuators started. Waiting for alerts...")

    try:
        while True:
            try:
                topic, msg = sub.receive(timeout_ms=100)
                if topic == "/drowsy/alert":
                    sim.process_alert_command(msg)
            except TimeoutError:
                continue
    except KeyboardInterrupt:
        print("\n[hmi.main] Shutting down...")
    finally:
        sub.close()

        # Post trip summary
        print("\n" + "=" * 50)
        print("Trip ended. Generating summary...")
        reporter = TripSummaryReporter(log_path=ROOT / "reports" / "alerts_log.jsonl")
        reporter.print_summary()
        sys.stdout.flush()


if __name__ == "__main__":
    main()

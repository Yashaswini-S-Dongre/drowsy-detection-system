#!/usr/bin/env python3
"""
mock_publisher.py
Publishes a JSON file repeatedly to a specified ZMQ/ROS topic to simulate a module's output.

Usage:
  python mock_publisher.py --topic /drowsy/alert --file ../contracts/sample_messages/alert_tier3.json --rate 1
"""
import argparse
import json
import time
import sys

def main():
    parser = argparse.ArgumentParser(description="Mock Publisher")
    parser.add_argument("--topic", required=True, help="Topic name (e.g., /drowsy/behavior)")
    parser.add_argument("--file", required=True, help="Path to golden sample JSON file")
    parser.add_argument("--rate", type=float, default=1.0, help="Publish rate in Hz")
    args = parser.parse_args()

    try:
        with open(args.file, 'r') as f:
            msg = json.load(f)
    except Exception as e:
        print(f"Error loading {args.file}: {e}")
        sys.exit(1)

    print(f"Starting mock publisher on {args.topic} at {args.rate} Hz...")
    print(f"Payload: {json.dumps(msg, indent=2)}")
    
    # In a real implementation, this would use ZMQ or rclpy
    # For phase 0, we just print to stdout to prove the contract works
    seq = 0
    try:
        while True:
            msg["seq"] = seq
            msg["ts"] = time.time() * 1000
            print(f"[{args.topic}] Pub: seq={seq}")
            seq += 1
            time.sleep(1.0 / args.rate)
    except KeyboardInterrupt:
        print("\nStopping mock publisher.")

if __name__ == "__main__":
    main()

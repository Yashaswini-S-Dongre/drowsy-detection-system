#!/usr/bin/env python3
"""
mock_subscriber.py
Subscribes to a specified ZMQ/ROS topic and prints received messages.

Usage:
  python mock_subscriber.py --topic /drowsy/alert
"""
import argparse
import time

def main():
    parser = argparse.ArgumentParser(description="Mock Subscriber")
    parser.add_argument("--topic", required=True, help="Topic name to subscribe to")
    args = parser.parse_args()

    print(f"Starting mock subscriber on {args.topic}...")
    
    # In a real implementation, this would use ZMQ or rclpy
    # For phase 0, this is a placeholder
    try:
        while True:
            time.sleep(1.0)
            # print(f"[{args.topic}] Sub: listening...")
    except KeyboardInterrupt:
        print("\nStopping mock subscriber.")

if __name__ == "__main__":
    main()

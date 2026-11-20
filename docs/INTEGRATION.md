# Integration Guide

This document defines how the four team folders connect and the correct run order.

## Folder Dependencies

All folders depend on the `/contracts` directory for message definitions and topics. They are otherwise entirely decoupled and communicate only via the `Bus` middleware abstraction (ROS 2 or ZeroMQ).

## Run Order (Simulator Mode)

To run the complete system on a developer machine without physical hardware:

1.  **Middleware/Bus**: Start the message broker (if using ZeroMQ fallback, start the central broker; if ROS 2, ensure `roscore`/daemon is running).
2.  **Fleet Stack (Optional)**: Start the Docker Compose stack in `04_hmi_alerts_fleet/fleet/` (Mosquitto, Node.js, InfluxDB).
3.  **Simulators**:
    *   Start the Vehicle simulator: `python -m 02_vehicle_physiological.simulators.vehicle_sim`
    *   Start the Physio generator (optional): `python -m 02_vehicle_physiological.simulators.physio_sim`
4.  **Processing Nodes**:
    *   Start Behavioral Vision: `python -m 01_behavioral_vision.main --source webcam`
    *   Start Vehicle Analysis: `python -m 02_vehicle_physiological.vehicle.main`
5.  **Fusion Engine**:
    *   Start Fusion Node: `python -m 03_fusion_edge_platform.fusion.main`
6.  **HMI**:
    *   Start the Qt/QML UI: `python -m 04_hmi_alerts_fleet.hmi_qml.main`

The script `scripts/run_all.sh` automates this startup sequence.

## Data Flow Verification

You can verify the integration by running the provided mock publishers/subscribers in `scripts/`.
For example, to verify the HMI responds to interventions, run the HMI and then:
`python scripts/mock_publisher.py --topic /drowsy/alert --file contracts/sample_messages/alert_tier3.json`

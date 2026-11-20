# System Architecture

## Block Diagram

```mermaid
flowchart TD
    subgraph Inputs ["Inputs (Sensors & Simulators)"]
        Cam[In-Cabin IR Camera / Webcam]
        ADAS[ADAS Camera / Lane Sim]
        EPS[EPS / CAN Bus Sim]
        Wear[Wearables / Physio Sim]
    end

    subgraph Processing ["Edge AI & Signal Processing (< 60 ms)"]
        Behav[Behavioural Analysis\n(EAR, MAR, PERCLOS, Pose)]
        Veh[Vehicle Behaviour\n(SWA ApEn, DTW, Lane Offset)]
        Physio[Physiological Analysis\n(EEG Theta/Alpha, HRV)]
    end

    subgraph Fusion ["Multi-Modal Fusion Engine"]
        Attn[Dynamic Attention Weighting]
        Model[two-layer Dense MLP (Multi-Layer Perceptron) Classifier]
        Redundancy[Redundancy & Quality Monitor]
    end

    subgraph Output ["Intervention & Alerting"]
        State[Intervention State Machine]
        HMI[Automotive HMI (Qt/QML)]
        Actuators[Actuator Simulators\n(Seatbelt, Hazards, ESA)]
        Fleet[Fleet Telemetry\n(Opt-in, Local MQTT)]
    end

    Cam --> Behav
    ADAS --> Veh
    EPS --> Veh
    Wear -. Optional .-> Physio

    Behav -->|BehaviorFeatures (~30Hz)| Fusion
    Veh -->|VehicleFeatures (~20Hz)| Fusion
    Physio -.->|PhysioFeatures (~1Hz)| Fusion

    Attn --> Model
    Redundancy --> Attn
    Model -->|FusionOutput (~10Hz)\n0=Alert, 1=Mild, 2=Mod, 3=Crit| State

    State -->|AlertCommand| HMI
    State -->|AlertCommand| Actuators
    State -->|TelemetryEvent| Fleet
```

## Timing Budget (Target: < 100 ms)

| Stage | Target Latency (p95) | Notes |
| :--- | :--- | :--- |
| **Frame Capture & Preprocessing** | 5 - 10 ms | OpenCV webcam read, CLAHE |
| **Landmark Detection** | 10 - 20 ms | MediaPipe Face Mesh |
| **Feature Extraction** | 5 - 10 ms | EAR, MAR, PERCLOS, solvePnP |
| **Behavioural Classification** | 5 - 15 ms | TFLite Inference |
| **Fusion Engine & State Machine** | 5 - 10 ms | Weighting, two-layer Dense MLP (Multi-Layer Perceptron), intervention logic |
| **HMI Rendering** | 16 ms | 60 FPS Qt rendering |
| **Total End-to-End** | **< 81 ms** | Safely under the 100 ms budget |

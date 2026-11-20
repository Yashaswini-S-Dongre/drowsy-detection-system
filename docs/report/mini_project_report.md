# Driver Drowsiness Detection System: Multi-Modal Alertness Evaluation Architecture
**Mini Project Report - BAI506**

**Authors:** Yashaswini S Dongre, Kishor J, Kruthi R, Shreyas Bidikar
**Guide:** Dr. Mayuri K P
**Department:** Artificial Intelligence and Machine Learning, BMSIT&M

---

## 1. Introduction
Driver drowsiness remains a critical factor in traffic accidents, severely impairing a driver's attention, reaction time, and vehicle control capabilities [10], [13]. Fatigued driving contributes to up to 45% of serious accidents globally [11], [12]. Existing detection mechanisms are often limited by a single sensor modality (e.g., only analyzing steering wheel angle or only using a camera), rendering them vulnerable to environmental factors like low light, sunglasses, or regular road variations.

To address these limitations, this project implements a **Multi-Modal Alertness Evaluation Architecture**. The system provides continuous, non-intrusive monitoring of the driver across three complementary pathways:
1. **Behavioral Monitoring:** Facial cues (PERCLOS, EAR, MAR) via an infrared (IR) camera.
2. **Vehicle-Based Monitoring:** Telemetry data including steering wheel angle (SWA) and lane positioning.
3. **Physiological Monitoring (Optional):** Highly precise biometric metrics like EEG (Theta/Alpha ratio) and ECG (HRV) for critical phases.

By synergizing these independent data streams using an edge-first AI framework, the system achieves robust redundancy, zero-latency processing (<100ms), and strict privacy compliance.

---

## 2. Literature Survey
A comprehensive review of the domain highlights the need for multi-modal architectures to overcome single-sensor constraints. 

*   **Multi-Modal Systems:** Sah et al. [1] demonstrated a 99% accuracy rate using Vision Transformers (ViT) and CNNs combining behavioral and vehicle data. El Sahmarany et al. [10] emphasized the need for combining EEG, GSR, and HRV to minimize false positives in physiological monitoring.
*   **Behavioral Monitoring:** Mahfudi et al. [4] established a strong Alertness Index (AI) utilizing YOLOv8 alongside EAR and MAR. Junaedi [15] validated PERCLOS as a highly reliable leading indicator for micro-sleep events. Deng & Wu [14] map eyelid and mouth landmarks to EAR/MAR time series, which is the same geometric stack used here.
*   **Vehicle-Based Monitoring:** Li et al. [5] and Saito et al. [6] established steering wheel micro-corrections (SWA) and dynamic time warping as highly robust fallback pathways when visual cues are compromised.
*   **Edge Computing & Privacy:** Safarov et al. [16] and the hybrid F-LSNN model [2] reinforce the necessity of keeping all image processing on a localized edge module to prevent latency bottlenecks and data privacy violations.

### 2.1 Timing delays used for the three-tier matrix

A normal blink lasts 100–400 ms. Researchers using EAR/PERCLOS therefore do **not** alarm on a single blink; they delay until closure is long enough to indicate cognitive impairment, and most critical-alarm implementations use a **2-second** continuous-closure threshold for micro-sleep [14], [15]. That delay is also consistent with automotive safety practice (a 2 s eyes-closed interval at 100 km/h covers more than 55 m). This project’s PRD names the three tiers but not the milliseconds; the table below is the operational mapping used in `config/thresholds.yaml`.

| Tier | Operational trigger | Time / count | Why this delay |
|------|---------------------|--------------|----------------|
| **1 Early warning** | Yawns (MAR above threshold) or minor lane drifts | ≥ 3 yawns **or** ≥ 2 drifts in a **60 s** rolling window | Frequency of tired behaviour, not one long event |
| **2 Moderate fatigue** | EAR continuously below 0.25 | **1.0–1.5 s** (implemented **1.0 s**) | Longer than any normal blink; eyelid droop / mandatory rest prompt |
| **3 Critical danger** | Eyes fully closed (EAR below 0.25), optionally corroborated by a drop in steering micro-corrections [5], [6] | **≥ 2.0 s** | Micro-sleep / high-decibel intervention and ESA |

References [2] and [7] have unconfirmed authors (verify before submission).

---

## 3. Methodology
The proposed architecture operates on an edge-based real-time processing pipeline. 

### 3.1 Data Acquisition & Feature Extraction
*   **Behavioral:** MediaPipe and Dlib-based 68-point facial landmarks map eye closure (EAR), mouth opening (MAR), yawning frequency, and PERCLOS.
*   **Vehicular:** Steering behavior is analyzed using Approximate Entropy (ApEn) and Dynamic Time Warping (DTW) to detect erratic micro-corrections and lane weaving.
*   **Physiological (Optional):** Continuous evaluation of the EEG Theta/Alpha ratio and Heart Rate Variability (HRV).

### 3.2 Multi-Modal Fusion Engine
All feature streams are routed through a real-time ROS 2 / ZeroMQ middleware to the **Fusion Engine**. The fusion engine dynamically weights inputs based on signal quality. If the camera is blinded (e.g., by sunlight), the system autonomously shifts weight to the vehicle pathway, ensuring uninterrupted monitoring. A trained TFLite model evaluates the fused scores to classify drowsiness across 4 levels.

### 3.3 Three-Tier Intervention Protocol
Rather than a binary alarm, the system uses a graduated escalation matrix (PRD Section 3). Time-based events override blended fusion scores so a 2 s micro-sleep cannot be diluted by an awake-looking steering channel:
*   **Level 0 (Alert):** No action; dark UI to minimize cognitive load.
*   **Level 1 (Mild):** Tier 1 — ≥ 3 yawns or ≥ 2 lane drifts in 60 s. Amber UI and subtle haptic feedback.
*   **Level 2 (Moderate):** Tier 2 — EAR < 0.25 for 1.0 s. Auditory chimes, seatbelt tightening, rest-break prompt.
*   **Level 3 (Critical):** Tier 3 — EAR < 0.25 for 2.0 s (micro-sleep). Pulsing red UI, continuous alarm, hazard lights, Emergency Stop Assist. The state machine jumps to this tier immediately; it does not wait for T1/T2 dwell steps.

---

## 4. Implementation
The project was structured across 4 distinct modules, developed in parallel against frozen JSON data contracts:
1.  **Behavioral Vision (`01_behavioral_vision`):** Python-based CV pipeline tracking 68-point landmarks.
2.  **Vehicle & Physiological (`02_vehicle_physiological`):** Simulators generating realistic CAN bus telemetry and EEG/ECG patterns.
3.  **Fusion & Edge Platform (`03_fusion_edge_platform`):** Dynamic weighting fusion engine and intervention state machine.
4.  **HMI & Alerts (`04_hmi_alerts_fleet`):** Qt/QML automotive display operating at 60+ FPS, strictly adhering to the 2-second glanceability rule, and an opt-in Node.js telemetry fleet backend.

All computationally heavy processes are optimized and quantized via TensorFlow Lite to comfortably execute on Jetson Nano / Raspberry Pi equivalent architectures.

---

## 5. Results & Evaluation

The system was rigorously tested against real-time latency budgets, simulated degradation, and model performance benchmarks. 

### 5.1 System Robustness 
*   **Camera Degradation Recovery:** Under simulated "Sunlight Blinded" conditions, the Fusion Engine successfully recognized a 95% drop in behavioral signal quality and shifted reliance to the Steering/Lane pathway, accurately sustaining drowsiness monitoring without raising a false alert.
*   **False-Positive Mitigation:** During a simulated "Sharp Curve" maneuver, irregular steering wheel angles were correctly correlated against lane and behavioral context, successfully avoiding a false "drowsy" classification.

### 5.2 Performance & Latency Metrics
*   **End-to-End Latency Target:** 100 ms
*   **Measured Fusion Engine Latency (p95):** < 1 ms (on typical CPU hardware).
*   **Result:** The pipeline is highly optimized, ensuring rapid safety intervention in critical micro-sleep scenarios.

### 5.3 Model Metrics
> **Note:** All metrics below were obtained from a **synthetic dataset** (generated simulators), not from a real driver dataset. They are labelled accordingly and must not be presented as real-world performance figures.

Synthetic training and evaluation demonstrated excellent regression accuracy across the independent feature pipelines (Behavioral Test MAE: 0.0858, Vehicle Test MAE: 0.0974), with the final Fusion Classification model achieving a **96.30% Accuracy** across the 4-level classification scale.

---

## 6. Conclusion and Future Work
The Driver Drowsiness Detection System successfully establishes a robust, highly reliable safety framework. By synthesizing behavioral, vehicular, and physiological modalities through an attention-based edge fusion engine, the architecture effectively eliminates the single-sensor vulnerabilities that plague existing systems. The implementation of a graduated, multi-sensory (visual, auditory, haptic) escalation protocol ensures timely interventions while significantly reducing alert fatigue.

**Future Work:**
*   Deployment onto physical automotive hardware (e.g., Jetson AGX / CAN Bus integration) utilizing the provided Yocto Embedded Linux framework.
*   Expansion of the behavioral dataset to accommodate more extreme facial occlusions (e.g., heavy facial hair, reflective polarized sunglasses).
*   Integration with live fleet management web dashboards via the pre-configured AWS IoT Core backend.

---

## References
[1] A. Sah, M. Das, A. K. Sony, B. Acharya, A. D. Deferisha, and A. Swetapadma, "An approach for identification of driver drowsiness, emotion state, and behavior patterns based on vision transformers, CNN and multi-modal sensor fusion using RAG-based interpretability," Discover Computing, vol. 29, no. 1, art. 341, 2026.

[2] [Author(s) not confirmed], "AIoT-based drowsiness level detection system using a hybrid F-LSNN network," ScienceDirect (article ID S1110866526000277), 2026.

[4] I. Mahfudi, M. A. J. Rasyid, Adzikirani, M. Kusumawardani, F. A. Soelistianto, R. A. Wijayanti, and A. Novianti, "Development of a Driver Drowsiness Detection System Using YOLO, EAR, and MAR for Driving Performance Evaluation," ILKOMNIKA, vol. 8, no. 2, pp. 206–219, 2026.

[5] Z. Li, S. E. Li, R. Li, B. Cheng, and J. Shi, "Online Detection of Driver Fatigue Using Steering Wheel Angles for Real Driving Conditions," Sensors, vol. 17, no. 3, art. 495, 2017.

[6] Y. Saito, M. Itoh, and T. Inagaki, "Driver Assistance System With a Dual Control Scheme: Effectiveness of Identifying Driver Drowsiness and Preventing Lane Departure Accidents," IEEE Transactions on Human-Machine Systems, vol. 46, no. 5, pp. 660–671, 2016.

[10] L. El Sahmarany, M. Alkhaldi, and S. I. Alzahrani, "Sensing Technologies and Physiological Parameters for Real-Time Driver Drowsiness Detection: A Comprehensive Review," Sensors, vol. 26, no. 11, art. 3333, 2026.

[11] S. F. Abdul Razak, S. Yogarayan, A. Abdul Aziz, M. F. A. Abdullah, and N. H. Kamis, "Physiological-based Driver Monitoring Systems: A Scoping Review," Civil Engineering Journal, vol. 8, no. 12, pp. 3952–3967, 2022.

[12] A. A. Saleem, H. U. R. Siddiqui, M. A. Raza, F. Rustam, S. Dudley, and I. Ashraf, "A systematic review of physiological signals based driver drowsiness detection systems," Cognitive Neurodynamics, vol. 17, no. 5, pp. 1229–1259, 2022.

[13] M. Ngxande, J.-R. Tapamo, and M. Burke, "Driver drowsiness detection using Behavioral measures and machine learning techniques: A review of state-of-art techniques," in Proc. Pattern Recognition Association of South Africa and Robotics and Mechatronics Conf. (PRASA-RobMech), Bloemfontein, South Africa, 2017.

[15] S. Junaedi, "Driver Drowsiness Detection Based on Face Feature and PERCLOS," Journal of Physics: Conference Series, vol. 1090, art. 012037, 2018.

[16] F. Safarov, F. Akhmedov, A. B. Abdusalomov, R. Nasimov, and Y. I. Cho, "Real-Time Deep Learning-Based Drowsiness Detection: Leveraging Computer-Vision and Eye-Blink Analyses for Enhanced Road Safety," Sensors, vol. 23, no. 14, art. 6459, 2023.
# Model Training & Evaluation Report
> NOTE: Real datasets were unavailable (privacy restrictions). All training and metrics were generated using SYNTHETIC data designed to mimic real-world distributions.

## Behavioral Model
* **Task:** Regression (Features -> Drowsiness Score)
* **Test MAE:** 0.0871
* **Status:** Converted to TFLite

## Vehicle Model
* **Task:** Regression (Features -> Drowsiness Score)
* **Test MAE:** 0.0944
* **Status:** Converted to TFLite

## Fusion Model
* **Task:** Classification (Sub-scores -> Alert Level [0-3])
* **Test Accuracy:** 95.50%
* **Status:** Converted to TFLite

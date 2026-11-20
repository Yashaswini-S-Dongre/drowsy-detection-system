"""
05_model_training/inference.py
==============================
Wrapper for TFLite inference.
Gracefully falls back to heuristic if models are not found or tflite is missing.
"""

import numpy as np
from pathlib import Path
from typing import Optional, Union, List

ROOT = Path(__file__).resolve().parents[1]

class TFLiteRunner:
    def __init__(self, model_path: Union[str, Path]):
        self.model_path = Path(model_path)
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self._init_interpreter()

    def _init_interpreter(self):
        if not self.model_path.exists():
            return

        try:
            # Try lightweight runtime first
            import tflite_runtime.interpreter as tflite
            Interpreter = tflite.Interpreter
        except ImportError:
            try:
                # Fallback to full TF
                import tensorflow as tf
                Interpreter = tf.lite.Interpreter
            except ImportError:
                return

        self.interpreter = Interpreter(model_path=str(self.model_path))
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

    def is_available(self) -> bool:
        """Return True if the TFLite interpreter was loaded successfully.

        Returns
        -------
        bool
            ``True`` when the model file exists and a TFLite runtime is
            installed; ``False`` otherwise.
        """
        return self.interpreter is not None

    def predict(self, input_features: List[float]) -> Optional[np.ndarray]:
        """Run one forward pass through the TFLite model.

        Parameters
        ----------
        input_features:
            Flat list of floats matching the model's expected input shape.

        Returns
        -------
        np.ndarray or None
            1-D output array from the model, or ``None`` if the interpreter
            is not available.
        """
        if not self.is_available():
            return None

        input_data = np.array([input_features], dtype=np.float32)
        self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
        self.interpreter.invoke()
        output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
        return output_data[0]


class ModelRegistry:
    """Singleton-like registry for loaded models."""
    _models = {}

    @classmethod
    def get_model(cls, name: str) -> TFLiteRunner:
        """Return (and cache) a TFLiteRunner for the named model.

        Path resolution note: ROOT = Path(__file__).resolve().parents[1] is the
        project root (one level above 05_model_training/).  train_pipeline.py
        writes models to ROOT_DIR / "models" where ROOT_DIR =
        Path(__file__).resolve().parent (= 05_model_training/).  Both therefore
        resolve to <project_root>/05_model_training/models/ — they match.
        """
        if name not in cls._models:
            # ROOT is the project root; models live inside 05_model_training/models/
            model_path = ROOT / "05_model_training" / "models" / f"{name}.tflite"
            cls._models[name] = TFLiteRunner(model_path)
        return cls._models[name]

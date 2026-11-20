"""
alert_outputs/actuator_sim.py
==============================
Simulates the physical actuators triggered by AlertCommand:
  - Haptic  (seat/wheel vibration) — synthesized via sounddevice
  - Audio   (chime / alarm)        — synthesized via sounddevice + system TTS
  - Visual  (terminal dashboard)   — ANSI-color rich console output
  - Seatbelt pretensioner          — logged + printed
  - Hazard lights                  — logged + printed
  - Emergency Stop Assist (ESA)    — logged + printed

All actuator events are:
  1. Logged with timestamp to an event log (for post-trip summary — Objective 4)
  2. Synchronised: all outputs from a single AlertCommand fire within one call
  3. Printed to stdout in demo/development mode

Three-tier alert system (PRD Section 3):
  Tier 1 – Early Warning  : visual (amber) + subtle haptic vibration pulse
  Tier 2 – Moderate Fatigue: prominent auditory chimes + strong haptic + seatbelt
  Tier 3 – Critical Danger : continuous alarm + voice TTS + hazard + ESA

PRIVACY: No raw biometrics are logged — only tier, timestamp, and actuator state.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

# sounddevice is installed in the drowsy_env
try:
    import sounddevice as sd
    _SD_AVAILABLE = True
except ImportError:
    _SD_AVAILABLE = False


# ---------------------------------------------------------------------------
# Audio synthesizers — real, non-synthetic audio output
# ---------------------------------------------------------------------------

_SAMPLE_RATE = 44100


def _play_nonblocking(signal: np.ndarray, fs: int = _SAMPLE_RATE) -> None:
    """Play a numpy audio array in a background thread (non-blocking)."""
    def _play():
        try:
            sd.play(signal.astype(np.float32), fs)
            sd.wait()
        except Exception:
            pass
    threading.Thread(target=_play, daemon=True).start()


def _synthesize_haptic_pulse(intensity: float = 0.3, duration_s: float = 0.4) -> np.ndarray:
    """
    Synthesize a vibration-like rumble tone for haptic simulation.
    Uses a 80–120 Hz binaural beat envelope to mimic seat/steering vibration.
    """
    fs = _SAMPLE_RATE
    t = np.linspace(0, duration_s, int(fs * duration_s))
    # Low-frequency rumble at 80 Hz with fast decay
    rumble = np.sin(2 * np.pi * 80 * t) * np.exp(-t * 8)
    # Modulate with 5 Hz envelope to create "pulsing" feel
    envelope = 0.5 * (1 + np.sin(2 * np.pi * 5 * t))
    signal = intensity * rumble * envelope
    return np.clip(signal, -1.0, 1.0).astype(np.float32)


def _synthesize_haptic_continuous(intensity: float = 1.0, duration_s: float = 1.5) -> np.ndarray:
    """
    Synthesize a strong continuous vibration pattern for Tier 3 haptic.
    """
    fs = _SAMPLE_RATE
    t = np.linspace(0, duration_s, int(fs * duration_s))
    # Harsh 120 Hz buzz
    buzz = np.sin(2 * np.pi * 120 * t)
    # Add harmonics for a more aggressive feel
    buzz += 0.4 * np.sin(2 * np.pi * 240 * t)
    buzz /= 1.4  # normalise
    # Rapid pulsing at 8 Hz
    pulse = 0.5 * (1 + np.sign(np.sin(2 * np.pi * 8 * t)))
    signal = intensity * buzz * pulse
    return np.clip(signal, -1.0, 1.0).astype(np.float32)


def _synthesize_chime(volume: float = 0.75) -> np.ndarray:
    """
    Tier 2: Three ascending musical chime notes (A4→E5→A5).
    Resembles a gentle but prominent automotive alert tone.
    """
    fs = _SAMPLE_RATE
    notes = [440.0, 659.25, 880.0]   # A4, E5, A5
    note_duration = 0.25              # seconds per note
    gap_duration  = 0.05             # silence between notes
    output_parts = []

    for freq in notes:
        n = int(fs * note_duration)
        t = np.linspace(0, note_duration, n)
        tone = np.sin(2 * np.pi * freq * t)
        # Bell-like decay
        envelope = np.exp(-t * 4.5)
        part = tone * envelope
        output_parts.append(part)
        output_parts.append(np.zeros(int(fs * gap_duration)))

    signal = np.concatenate(output_parts)
    return (volume * signal / (np.max(np.abs(signal)) + 1e-9)).astype(np.float32)


def _synthesize_alarm(volume: float = 1.0, duration_s: float = 2.0) -> np.ndarray:
    """
    Tier 3: Continuous high-decibel two-tone alarm (UK-style 770 / 660 Hz alternating).
    """
    fs = _SAMPLE_RATE
    n  = int(fs * duration_s)
    t  = np.linspace(0, duration_s, n)
    # Two-tone alternating at 3.5 Hz switch rate
    switch_mask = np.sign(np.sin(2 * np.pi * 3.5 * t))  # +1 / -1
    freq_mod    = np.where(switch_mask > 0, 770.0, 660.0)
    # Numerically stable instantaneous phase
    phase = 2 * np.pi * np.cumsum(freq_mod) / fs
    alarm = np.sin(phase)
    return (volume * alarm).astype(np.float32)


def _play_tts(message: str) -> None:
    """
    macOS/Linux TTS voice warning (non-blocking subprocess).
    Falls back silently on unsupported platforms.
    """
    def _tts():
        try:
            # macOS
            subprocess.run(
                ["say", "-v", "Samantha", "-r", "160", message],
                timeout=6,
                check=False,
            )
        except FileNotFoundError:
            try:
                # Linux (espeak)
                subprocess.run(
                    ["espeak", message],
                    timeout=6, check=False,
                )
            except FileNotFoundError:
                pass
    threading.Thread(target=_tts, daemon=True).start()


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ActuatorEvent:
    """One timestamped actuator activation record."""
    ts_ms:                 float
    tier:                  int
    seatbelt_tighten:      bool
    hazard_lights:         bool
    emergency_stop_assist: bool
    haptic_pattern:        str
    haptic_intensity:      float
    audio_type:            str
    audio_volume:          float
    alert_message:         str


# ---------------------------------------------------------------------------
# ActuatorSimulator
# ---------------------------------------------------------------------------

class ActuatorSimulator:
    """
    Simulates physical actuators and maintains a local event log.

    Parameters
    ----------
    log_path : Path or None
        If set, appends all actuator events to a JSONL file.
    verbose : bool
        Print a human-readable summary for each event in demo mode.
    """

    # ANSI colour table per tier
    _COLORS = {
        0: "\033[90m",   # grey  — nominal/monitoring
        1: "\033[93m",   # amber — Tier 1
        2: "\033[33m",   # dark amber — Tier 2
        3: "\033[91m",   # red  — Tier 3 CRITICAL
    }
    _RESET = "\033[0m"

    def __init__(
        self,
        log_path: Optional[Path] = None,
        verbose: bool = True,
    ) -> None:
        self._log_path = log_path
        self._verbose  = verbose
        self._events:  list[ActuatorEvent] = []
        self._active_tier: int = 0
        self._last_audio_ts: float = 0.0  # throttle audio to prevent overlap

        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------

    def process_alert_command(self, cmd: dict[str, Any]) -> ActuatorEvent:
        """
        Process one AlertCommand dict and simulate all actuator outputs.

        All modalities (visual, audio, haptic, seatbelt, hazard, ESA)
        fire synchronously within this call as per the PRD 3-tier protocol.

        Returns
        -------
        ActuatorEvent  — the logged event record.
        """
        tier      = cmd.get("tier", 0)
        ts_ms     = cmd.get("ts", time.time() * 1000.0)
        audio     = cmd.get("audio", {})
        haptic    = cmd.get("haptic", {})
        visual    = cmd.get("visual", {})

        event = ActuatorEvent(
            ts_ms                 = ts_ms,
            tier                  = tier,
            seatbelt_tighten      = bool(cmd.get("seatbelt_tighten", False)),
            hazard_lights         = bool(cmd.get("hazard_lights", False)),
            emergency_stop_assist = bool(cmd.get("emergency_stop_assist", False)),
            haptic_pattern        = str(haptic.get("pattern", "none")),
            haptic_intensity      = float(haptic.get("intensity", 0.0)),
            audio_type            = str(audio.get("type", "none")),
            audio_volume          = float(audio.get("volume", 0.0)),
            alert_message         = str(visual.get("message", "")),
        )

        # Fire all actuators (order: visual first → haptic → audio → safety)
        self._simulate_visual(event)
        self._simulate_haptic(event)
        self._simulate_audio(event, ts_ms)
        self._simulate_seatbelt(event)
        self._simulate_hazard_lights(event)
        self._simulate_esa(event)

        # Log
        self._events.append(event)
        self._log_event(event)
        self._active_tier = tier

        return event

    @property
    def event_log(self) -> list[ActuatorEvent]:
        return list(self._events)

    @property
    def active_tier(self) -> int:
        return self._active_tier

    # ------------------------------------------------------------------
    # Actuator simulators — each corresponds to a real actuator
    # ------------------------------------------------------------------

    def _simulate_visual(self, e: ActuatorEvent) -> None:
        """
        Visual HMI alert — tier-colour ANSI dashboard block.
        Maps to automotive HMI colour scheme from tech stack doc:
          Blue/Green → monitoring, Amber → Tier 1/2, Red → Tier 3.
        """
        if e.tier == 0:
            if self._verbose:
                print(f"{self._COLORS[0]}[VISUAL] ● System monitoring — driver alert{self._RESET}")
        else:
            color = self._COLORS.get(e.tier, self._COLORS[3])
            if self._verbose:
                tier_labels = {
                    1: "⚠  TIER 1 — EARLY WARNING",
                    2: "⚠⚠ TIER 2 — MODERATE FATIGUE",
                    3: "🛑 TIER 3 — CRITICAL DANGER",
                }
                label = tier_labels.get(e.tier, f"TIER {e.tier}")
                print(f"\n{color}{'='*60}")
                print(f"  [VISUAL] {label}")
                print(f"  Message : {e.alert_message}")
                print(f"{'='*60}{self._RESET}\n")

        # Draw OpenCV window for visual UI
        try:
            import cv2
            import numpy as np

            if e.tier == 0:
                try:
                    cv2.destroyWindow("HMI Alert Dashboard")
                except cv2.error:
                    pass
                if hasattr(self, "_current_frame"):
                    del self._current_frame
                cv2.waitKey(1)
                return

            img = np.zeros((300, 500, 3), dtype=np.uint8)
            img[:] = (30, 30, 30)

            if e.tier == 1:
                cv2.rectangle(img, (0, 0), (500, 300), (0, 140, 255), 10)
                cv2.putText(img, "DROWSINESS DETECTED", (80, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 140, 255), 2)
                # Draw steering wheel
                cv2.circle(img, (250, 180), 50, (0, 140, 255), 6)
                cv2.circle(img, (250, 180), 20, (0, 140, 255), -1)
                cv2.line(img, (200, 180), (230, 180), (0, 140, 255), 6)
                cv2.line(img, (270, 180), (300, 180), (0, 140, 255), 6)
                cv2.line(img, (250, 200), (250, 230), (0, 140, 255), 6)
            elif e.tier == 2:
                cv2.rectangle(img, (0, 0), (500, 300), (0, 100, 255), 20)
                cv2.putText(img, "TAKE A BREAK", (120, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 100, 255), 3)
                # Draw Coffee Cup
                cv2.rectangle(img, (210, 150), (270, 220), (0, 100, 255), -1) # Cup body
                cv2.ellipse(img, (270, 185), (20, 20), 0, -90, 90, (0, 100, 255), 6) # Cup handle
                # Steam
                cv2.line(img, (225, 140), (225, 120), (0, 100, 255), 3)
                cv2.line(img, (240, 135), (240, 115), (0, 100, 255), 3)
                cv2.line(img, (255, 140), (255, 120), (0, 100, 255), 3)
            elif e.tier == 3:
                cv2.rectangle(img, (0, 0), (500, 300), (0, 0, 255), 30)
                cv2.putText(img, "CRITICAL DANGER!", (80, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
                cv2.putText(img, "PULL OVER NOW", (100, 130), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
                # Draw Exclamation Warning
                pts = np.array([[250, 150], [200, 240], [300, 240]], np.int32)
                cv2.fillPoly(img, [pts], (0, 0, 255))
                cv2.circle(img, (250, 230), 5, (30, 30, 30), -1)
                cv2.line(img, (250, 175), (250, 210), (30, 30, 30), 6)

            self._current_frame = img
            cv2.imshow("HMI Alert Dashboard", img)
            cv2.waitKey(1)
        except ImportError:
            pass

    def update_gui(self):
        """Called repeatedly to keep the OpenCV window responsive."""
        try:
            import cv2
            if hasattr(self, "_current_frame"):
                cv2.imshow("HMI Alert Dashboard", self._current_frame)
                cv2.waitKey(1)
        except ImportError:
            pass

    def _simulate_haptic(self, e: ActuatorEvent) -> None:
        """
        Haptic actuator — synthesized vibration tone via sounddevice.
        Tier 1: subtle pulse (80 Hz, 0.4 s).
        Tier 2: strong pulse (80 Hz + 120 Hz, 0.6 s).
        Tier 3: continuous aggressive buzz (120 Hz + harmonics, 1.5 s).
        """
        if e.haptic_pattern == "none":
            return

        if self._verbose:
            icons = {
                "subtle_pulse":  "〜",
                "strong_pulse":  "〜〜",
                "continuous":    "〜〜〜",
            }
            icon = icons.get(e.haptic_pattern, "〜")
            print(f"[HAPTIC] {icon} pattern={e.haptic_pattern} "
                  f"intensity={e.haptic_intensity:.1f} (Tier {e.tier})")

        if _SD_AVAILABLE:
            if e.haptic_pattern == "continuous":
                signal = _synthesize_haptic_continuous(intensity=e.haptic_intensity)
            else:
                signal = _synthesize_haptic_pulse(intensity=e.haptic_intensity)
            _play_nonblocking(signal)

    def _simulate_audio(self, e: ActuatorEvent, ts_ms: float) -> None:
        """
        Audio actuator — synthesized sounds via sounddevice.
        Tier 2: 3-note ascending chime (A4→E5→A5).
        Tier 3: two-tone siren + TTS voice warning.
        Throttled to prevent audio overlap: minimum 3 s between sounds.
        """
        if e.audio_type == "none":
            return

        now_s = ts_ms / 1000.0
        audio_throttle_s = 3.0 if e.audio_type == "chime" else 6.0
        if (now_s - self._last_audio_ts) < audio_throttle_s:
            return
        self._last_audio_ts = now_s

        if self._verbose:
            symbol = "🔔" if e.audio_type == "chime" else "🚨"
            print(f"[AUDIO]  {symbol} type={e.audio_type} volume={e.audio_volume:.1f}")

        if _SD_AVAILABLE:
            if e.audio_type == "chime":
                signal = _synthesize_chime(volume=e.audio_volume)
                _play_nonblocking(signal)
                if e.tier == 2:
                    _play_tts("Please take a break. Moderate fatigue detected.")
            elif e.audio_type == "alarm_continuous":
                signal = _synthesize_alarm(volume=e.audio_volume)
                _play_nonblocking(signal)
                _play_tts("Warning. Critical drowsiness detected. Pull over now safely.")

    def _simulate_seatbelt(self, e: ActuatorEvent) -> None:
        """Seatbelt pretensioner — Tier 2 and Tier 3."""
        if not e.seatbelt_tighten:
            return
        if self._verbose:
            print(f"[SEATBELT] 🔒 Pretensioner activated — Tier {e.tier}")

    def _simulate_hazard_lights(self, e: ActuatorEvent) -> None:
        """Hazard light activation — Tier 3 only."""
        if not e.hazard_lights:
            return
        if self._verbose:
            print(f"[HAZARD LIGHTS] ⚠ Hazard lights activated — Tier {e.tier}")

    def _simulate_esa(self, e: ActuatorEvent) -> None:
        """Emergency Stop Assist — Tier 3 only."""
        if not e.emergency_stop_assist:
            return
        if self._verbose:
            print(f"[ESA] 🛑 Emergency Stop Assist triggered — Tier {e.tier}")

    def _log_event(self, e: ActuatorEvent) -> None:
        record = {
            "ts_ms":    e.ts_ms,
            "tier":     e.tier,
            "seatbelt": e.seatbelt_tighten,
            "hazard":   e.hazard_lights,
            "esa":      e.emergency_stop_assist,
            "haptic":   e.haptic_pattern,
            "audio":    e.audio_type,
            "message":  e.alert_message,
        }
        if self._log_path:
            with open(self._log_path, "a") as f:
                f.write(json.dumps(record) + "\n")


# ---------------------------------------------------------------------------
# Post-trip summary report generator (Objective 4)
# ---------------------------------------------------------------------------

class TripSummaryReporter:
    """
    Reads the actuator event log and generates a post-trip drowsiness summary.

    Usage
    -----
        reporter = TripSummaryReporter(log_path=Path("reports/alerts.jsonl"))
        reporter.print_summary()
    """

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path

    def load_events(self) -> list[dict[str, Any]]:
        if not self._log_path.exists():
            return []
        events = []
        with open(self._log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events

    def generate_summary(self) -> dict[str, Any]:
        events = self.load_events()
        if not events:
            return {"status": "No events recorded", "events": 0}

        tier_counts: dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0}
        for e in events:
            t = e.get("tier", 0)
            tier_counts[t] = tier_counts.get(t, 0) + 1

        first_ts = events[0]["ts_ms"]
        last_ts  = events[-1]["ts_ms"]
        duration_min = (last_ts - first_ts) / 60_000.0

        return {
            "trip_duration_min":  round(duration_min, 1),
            "total_alerts":       len(events),
            "tier1_alerts":       tier_counts.get(1, 0),
            "tier2_alerts":       tier_counts.get(2, 0),
            "tier3_alerts":       tier_counts.get(3, 0),
            "overall_alertness":  self._alertness_rating(tier_counts, len(events)),
            "recommendation":     self._recommendation(tier_counts),
        }

    @staticmethod
    def _alertness_rating(tier_counts: dict, total: int) -> str:
        if tier_counts.get(3, 0) > 0:
            return "CRITICAL — Driver experienced severe drowsiness"
        elif tier_counts.get(2, 0) > 2:
            return "POOR — Frequent moderate fatigue detected"
        elif tier_counts.get(1, 0) > 5:
            return "FAIR — Mild drowsiness detected"
        elif total == 0:
            return "EXCELLENT — No drowsiness events"
        else:
            return "GOOD — Minor drowsiness, well managed"

    @staticmethod
    def _recommendation(tier_counts: dict) -> str:
        if tier_counts.get(3, 0) > 0:
            return "Avoid driving until well rested. Consult a physician if this is frequent."
        elif tier_counts.get(2, 0) > 0:
            return "Plan mandatory rest stops for future long drives."
        else:
            return "Consider taking a break earlier on long journeys."

    def print_summary(self) -> None:
        s = self.generate_summary()
        print("\n" + "="*50)
        print("  POST-TRIP DROWSINESS SUMMARY")
        print("="*50)
        for k, v in s.items():
            print(f"  {k:<25}: {v}")
        print("="*50 + "\n")

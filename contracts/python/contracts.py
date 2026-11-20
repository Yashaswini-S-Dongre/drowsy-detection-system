"""
contracts/python/contracts.py
==============================
Pydantic v2 models generated from the JSON schemas in contracts/schemas/.
READ-ONLY after Phase 0 freeze. Changes require a PR approved by all four owners.

Usage
-----
    from contracts.python.contracts import (
        BehaviorFeatures, VehicleFeatures, PhysioFeatures,
        FusionOutput, AlertCommand, SystemStatus, TelemetryEvent,
        DrowsinessLevel, AlertTier, AudioType, HapticPattern,
        PathwayHealth, VisualSpec, AudioSpec, HapticSpec,
        ModalityWeights, PathwayHealthMap, ConsentState,
        StageLatency,
    )

All models use `model_config = ConfigDict(extra="forbid")` to mirror
`additionalProperties: false` in the schemas.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Annotated, List, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class DrowsinessLevel(IntEnum):
    """4-level drowsiness classifier output (synopsis Section 4, Step 5)."""
    ALERT    = 0  # normal driving – dark UI
    MILD     = 1  # Tier 1 intervention
    MODERATE = 2  # Tier 2 intervention
    CRITICAL = 3  # Tier 3 intervention


class AlertTier(IntEnum):
    """Intervention tier mapped from DrowsinessLevel."""
    NONE     = 0
    EARLY    = 1  # gentle visual + subtle haptic
    MODERATE = 2  # auditory chimes + seatbelt + rest prompt
    CRITICAL = 3  # continuous alarm + hazard lights + ESA


class AudioType(str):
    NONE             = "none"
    CHIME            = "chime"
    ALARM_CONTINUOUS = "alarm_continuous"


class HapticPattern(str):
    NONE          = "none"
    SUBTLE_PULSE  = "subtle_pulse"
    STRONG_PULSE  = "strong_pulse"
    CONTINUOUS    = "continuous"


class PathwayHealth(str):
    OK       = "ok"
    DEGRADED = "degraded"
    FAILED   = "failed"
    DISABLED = "disabled"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class StageLatency(BaseModel):
    """Per-stage latency breakdown within the behavioural pipeline."""
    model_config = ConfigDict(extra="forbid")

    capture:   Annotated[float, Field(ge=0, description="Frame capture latency (ms)")]
    landmarks: Annotated[float, Field(ge=0, description="Landmark detection latency (ms)")]
    features:  Annotated[float, Field(ge=0, description="Feature extraction latency (ms)")]
    model:     Annotated[float, Field(ge=0, description="TFLite inference latency (ms)")]


class ModalityWeights(BaseModel):
    """Dynamic attention weights used by the fusion engine."""
    model_config = ConfigDict(extra="forbid")

    behavior: Annotated[float, Field(ge=0, le=1)]
    vehicle:  Annotated[float, Field(ge=0, le=1)]
    physio:   Annotated[float, Field(ge=0, le=1)]


class PathwayHealthMap(BaseModel):
    """Health state for each monitoring pathway."""
    model_config = ConfigDict(extra="forbid")

    behavior: Literal["ok", "degraded", "failed", "disabled"]
    vehicle:  Literal["ok", "degraded", "failed", "disabled"]
    physio:   Literal["ok", "degraded", "failed", "disabled"]


class ConsentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telemetry_opt_in: bool = Field(
        False, description="True only after explicit driver consent"
    )


class VisualSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color:     str = Field(description="Hex/CSS color or semantic name")
    message:   str = Field(max_length=40, description="Short glanceable driver message")
    animation: str = Field(description="Lottie JSON filename or 'none'")


class AudioSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type:   Literal["none", "chime", "alarm_continuous"]
    volume: Annotated[float, Field(ge=0, le=1)]


class HapticSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern:   Literal["none", "subtle_pulse", "strong_pulse", "continuous"]
    intensity: Annotated[float, Field(ge=0, le=1)]


# ---------------------------------------------------------------------------
# Primary message models
# ---------------------------------------------------------------------------

class BehaviorFeatures(BaseModel):
    """
    Published at ~30 Hz by 01_behavioral_vision on /drowsy/behavior.
    Source: BehaviorFeatures.json schema.
    """
    model_config = ConfigDict(extra="forbid")

    ts:    float = Field(description="Epoch timestamp (ms)")
    seq:   int   = Field(ge=0, description="Monotonic sequence number")

    # Frame metadata
    frame_id:     int   = Field(ge=0)
    face_detected: bool
    quality:      Annotated[float, Field(ge=0, le=1)]

    # Eye metrics
    ear_left:           Annotated[float, Field(ge=0)]
    ear_right:          Annotated[float, Field(ge=0)]
    ear_mean:           Annotated[float, Field(ge=0)]
    blink_rate_per_min: Annotated[float, Field(ge=0)]
    blink_duration_ms:  Annotated[float, Field(ge=0)]
    perclos_60s:        Annotated[float, Field(ge=0, le=1, description="PERCLOS over 60 s window")]

    # Mouth / yawn
    mar:             Annotated[float, Field(ge=0)]
    yawn_active:     bool
    yawn_count_5min: Annotated[int,   Field(ge=0)]

    # Gaze
    gaze_yaw:           float
    gaze_pitch:         float
    gaze_off_road_ratio: Annotated[float, Field(ge=0, le=1)]

    # Head pose (solvePnP)
    head_pitch:    float
    head_yaw:      float
    head_roll:     float
    head_nod_event: bool

    # Composite score
    behavior_score: Annotated[float, Field(ge=0, le=1)]

    # Profiling
    stage_latency_ms: StageLatency


class VehicleFeatures(BaseModel):
    """
    Published at ~20 Hz by 02_vehicle_physiological on /drowsy/vehicle.
    Source: VehicleFeatures.json schema.
    """
    model_config = ConfigDict(extra="forbid")

    ts:  float = Field(description="Epoch timestamp (ms)")
    seq: int   = Field(ge=0)

    # Steering (EPS / CAN simulator)
    swa_deg:               float
    swa_rate:              float
    micro_correction_rate: Annotated[float, Field(ge=0)]
    swa_approx_entropy:    Annotated[float, Field(ge=0)]
    dtw_dist_awake:        Annotated[float, Field(ge=0)]
    dtw_dist_drowsy:       Annotated[float, Field(ge=0)]

    # Lane (ADAS / lane simulator)
    lane_offset_m:        float
    lane_departure_count: Annotated[int,   Field(ge=0)]
    weaving_index:        Annotated[float, Field(ge=0)]
    lane_confidence:      Annotated[float, Field(ge=0, le=1)]

    # Context
    speed_kph:      Annotated[float, Field(ge=0)]
    road_curvature: float

    # Pathway quality & score
    quality:       Annotated[float, Field(ge=0, le=1)]
    vehicle_score: Annotated[float, Field(ge=0, le=1)]


class PhysioFeatures(BaseModel):
    """
    Published at ~1 Hz by 02_vehicle_physiological on /drowsy/physio.
    available=False when physio.enabled=false in config.
    Source: PhysioFeatures.json schema.
    """
    model_config = ConfigDict(extra="forbid")

    ts:  float = Field(description="Epoch timestamp (ms)")
    seq: int   = Field(ge=0)

    available: bool

    # EEG
    theta_alpha_ratio: Annotated[float, Field(ge=0)]
    beta_power:        Annotated[float, Field(ge=0)]

    # ECG / HRV
    hr_bpm:    Annotated[float, Field(ge=0)]
    hrv_rmssd: Annotated[float, Field(ge=0)]
    hrv_lf_hf: Annotated[float, Field(ge=0)]

    quality:      Annotated[float, Field(ge=0, le=1)]
    physio_score: Annotated[float, Field(ge=0, le=1)]


class FusionOutput(BaseModel):
    """
    Published at ~10 Hz by 03_fusion_edge_platform on /drowsy/fusion.
    Primary output driving interventions. total_latency_ms must be <100 ms at p95.
    Source: FusionOutput.json schema.
    """
    model_config = ConfigDict(extra="forbid")

    ts:  float = Field(description="Epoch timestamp (ms)")
    seq: int   = Field(ge=0)

    level:            DrowsinessLevel
    drowsiness_score: Annotated[float, Field(ge=0, le=1)]
    confidence:       Annotated[float, Field(ge=0, le=1)]

    per_modality_weights: ModalityWeights
    active_pathways:      List[Literal["behavior", "vehicle", "physio"]]

    degraded_mode: bool
    reason_codes:  List[str]

    total_latency_ms: Annotated[float, Field(ge=0, description="End-to-end latency (ms)")]


class AlertCommand(BaseModel):
    """
    Event emitted by the intervention state machine on /drowsy/alert.
    Tier mapping: 0=dark UI, 1=Tier1 (Mild), 2=Tier2 (Moderate), 3=Tier3 (Critical).
    Source: AlertCommand.json schema.
    """
    model_config = ConfigDict(extra="forbid")

    ts:        float = Field(description="Epoch timestamp (ms)")
    seq:       int   = Field(ge=0)
    timestamp: float = Field(description="Alias for ts, for HMI convenience")

    tier: AlertTier

    visual: VisualSpec
    audio:  AudioSpec
    haptic: HapticSpec

    seatbelt_tighten:      bool  # Tier 2+
    hazard_lights:         bool  # Tier 3 only
    emergency_stop_assist: bool  # Tier 3 only
    rest_break_prompt:     bool  # Tier 2+


class SystemStatus(BaseModel):
    """
    1 Hz health heartbeat published by 03_fusion_edge_platform on /drowsy/status.
    Source: SystemStatus.json schema.
    """
    model_config = ConfigDict(extra="forbid")

    ts:  float = Field(description="Epoch timestamp (ms)")
    seq: int   = Field(ge=0)

    pathway_health: PathwayHealthMap
    consent:        ConsentState

    fps:     Annotated[float, Field(ge=0)]
    cpu_pct: Annotated[float, Field(ge=0, le=100)]

    model_versions: dict[str, str] = Field(
        default_factory=dict,
        description="Version strings for deployed TFLite models"
    )


class TelemetryEvent(BaseModel):
    """
    Opt-in fleet telemetry event on /drowsy/telemetry.
    Published by 04_hmi_alerts_fleet ONLY when consent.telemetry_opt_in=True.
    PRIVACY: Contains NO raw biometrics (no EAR/MAR/PERCLOS/EEG/ECG values).
    Source: TelemetryEvent.json schema.
    """
    model_config = ConfigDict(extra="forbid")

    ts:  float = Field(description="Epoch timestamp (ms)")
    seq: int   = Field(ge=0)

    vehicle_id: str  = Field(description="Anonymised vehicle ID – not PII")
    event_type: Literal["drowsiness_event", "pathway_degraded", "recovery"]
    tier:       AlertTier
    duration_s: Annotated[float, Field(ge=0)]


# ---------------------------------------------------------------------------
# Re-exports for convenience
# ---------------------------------------------------------------------------

__all__ = [
    "DrowsinessLevel", "AlertTier", "AudioType", "HapticPattern", "PathwayHealth",
    "StageLatency", "ModalityWeights", "PathwayHealthMap", "ConsentState",
    "VisualSpec", "AudioSpec", "HapticSpec",
    "BehaviorFeatures", "VehicleFeatures", "PhysioFeatures",
    "FusionOutput", "AlertCommand", "SystemStatus", "TelemetryEvent",
]

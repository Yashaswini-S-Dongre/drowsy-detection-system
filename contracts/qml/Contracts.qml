// contracts/qml/Contracts.qml
// ============================================================
// QML singleton exposing alert tiers, colours, topic names,
// and message field constants derived from the contracts.
// READ-ONLY after Phase 0 freeze.
//
// Usage in QML:
//   import "qrc:/contracts/qml"
//   Rectangle { color: Contracts.tierColor(Contracts.TIER_CRITICAL) }
// ============================================================

pragma Singleton
import QtQuick 2.15

QtObject {

    // ── Drowsiness / Alert tiers ────────────────────────────
    readonly property int TIER_NONE:     0   // Alert  – dark UI
    readonly property int TIER_EARLY:    1   // Mild   – Tier 1
    readonly property int TIER_MODERATE: 2   // Moderate – Tier 2
    readonly property int TIER_CRITICAL: 3   // Critical – Tier 3

    // ── Canonical colour palette (synopsis §7 & Design Doc) ─
    // Monitoring / idle
    readonly property color COLOR_MONITORING: "#22c55e"   // blue-green
    // Tier 1 / Tier 2 early warning
    readonly property color COLOR_AMBER:      "#f59e0b"   // amber
    // Tier 3 critical danger
    readonly property color COLOR_RED:        "#ef4444"   // high-contrast red
    // Dark UI background (normal driving)
    readonly property color COLOR_DARK_BG:    "#0a0a0a"
    // Status glyph inactive
    readonly property color COLOR_INACTIVE:   "#1f2937"

    // ── Topic names (must match topics.yaml) ────────────────
    readonly property string TOPIC_BEHAVIOR:  "/drowsy/behavior"
    readonly property string TOPIC_VEHICLE:   "/drowsy/vehicle"
    readonly property string TOPIC_PHYSIO:    "/drowsy/physio"
    readonly property string TOPIC_FUSION:    "/drowsy/fusion"
    readonly property string TOPIC_ALERT:     "/drowsy/alert"
    readonly property string TOPIC_STATUS:    "/drowsy/status"
    readonly property string TOPIC_TELEMETRY: "/drowsy/telemetry"

    // ── Pathway health enum strings ──────────────────────────
    readonly property string HEALTH_OK:       "ok"
    readonly property string HEALTH_DEGRADED: "degraded"
    readonly property string HEALTH_FAILED:   "failed"
    readonly property string HEALTH_DISABLED: "disabled"

    // ── Audio types ──────────────────────────────────────────
    readonly property string AUDIO_NONE:             "none"
    readonly property string AUDIO_CHIME:            "chime"
    readonly property string AUDIO_ALARM_CONTINUOUS: "alarm_continuous"

    // ── Haptic patterns ──────────────────────────────────────
    readonly property string HAPTIC_NONE:         "none"
    readonly property string HAPTIC_SUBTLE_PULSE: "subtle_pulse"
    readonly property string HAPTIC_STRONG_PULSE: "strong_pulse"
    readonly property string HAPTIC_CONTINUOUS:   "continuous"

    // ── Helper: resolve tier → background colour ────────────
    function tierColor(tier) {
        switch (tier) {
            case TIER_EARLY:    return COLOR_AMBER
            case TIER_MODERATE: return COLOR_AMBER
            case TIER_CRITICAL: return COLOR_RED
            default:            return COLOR_DARK_BG
        }
    }

    // ── Helper: resolve tier → display label ────────────────
    function tierLabel(tier) {
        switch (tier) {
            case TIER_EARLY:    return "DROWSINESS DETECTED"
            case TIER_MODERATE: return "MODERATE FATIGUE – TAKE A BREAK"
            case TIER_CRITICAL: return "⚠ CRITICAL – PULL OVER NOW"
            default:            return ""
        }
    }

    // ── Helper: resolve health string → indicator colour ────
    function healthColor(status) {
        switch (status) {
            case HEALTH_OK:       return COLOR_MONITORING
            case HEALTH_DEGRADED: return COLOR_AMBER
            case HEALTH_FAILED:   return COLOR_RED
            default:              return COLOR_INACTIVE
        }
    }
}

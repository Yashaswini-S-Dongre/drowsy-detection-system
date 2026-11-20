"""
04_hmi_alerts_fleet/fleet/telemetry_publisher.py
=================================================
Opt-in fleet telemetry publisher.

Subscribes to the fusion output topic via ZMQ and forwards anonymised
TelemetryEvent payloads to a local MQTT broker.  No raw biometrics are
ever transmitted — only tier, timestamp, and event duration.

Privacy gate: nothing is published unless ``telemetry.opt_in_default``
is ``true`` in ``config/privacy.yaml``.

Run standalone::

    python 04_hmi_alerts_fleet/fleet/telemetry_publisher.py

"""
from __future__ import annotations

import json
import logging
import time
import uuid
import warnings
from pathlib import Path
from typing import Optional

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parents[2]
_CONFIG_DIR = _PROJECT_ROOT / "config"
_VEHICLE_ID_FILE = _CONFIG_DIR / ".vehicle_id"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    """Load and return a YAML file as a dict.

    Parameters
    ----------
    path:
        Absolute path to the YAML file.

    Returns
    -------
    dict
        Parsed YAML content.
    """
    with open(path) as fh:
        return yaml.safe_load(fh)


def _get_or_create_vehicle_id() -> str:
    """Return a stable anonymous UUID for this installation.

    The UUID is stored in ``config/.vehicle_id`` so it persists across
    restarts while remaining meaningless as PII.  A fresh UUID is
    generated on first call.

    Returns
    -------
    str
        UUID4 string (e.g. ``"a3f1c2d4-..."``)
    """
    if _VEHICLE_ID_FILE.exists():
        return _VEHICLE_ID_FILE.read_text().strip()
    new_id = str(uuid.uuid4())
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _VEHICLE_ID_FILE.write_text(new_id)
    logger.info("Generated anonymous vehicle_id: %s", new_id)
    return new_id


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class TelemetryPublisher:
    """Subscribe to fusion output and publish anonymised telemetry events.

    All configuration is loaded from YAML files — no hardcoded values.

    Parameters
    ----------
    config_dir:
        Directory containing ``default.yaml``, ``privacy.yaml``.
        Defaults to ``<project_root>/config/``.
    contracts_dir:
        Directory containing ``topics.yaml``.
        Defaults to ``<project_root>/contracts/``.
    """

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        contracts_dir: Optional[Path] = None,
    ) -> None:
        self._config_dir = config_dir or _CONFIG_DIR
        self._contracts_dir = contracts_dir or (_PROJECT_ROOT / "contracts")

        # Load all config
        self._default_cfg = _load_yaml(self._config_dir / "default.yaml")
        self._privacy_cfg = _load_yaml(self._config_dir / "privacy.yaml")
        self._topics_cfg = _load_yaml(self._contracts_dir / "topics.yaml")

        # Privacy gate
        self._opt_in: bool = bool(
            self._privacy_cfg.get("telemetry", {}).get("opt_in_default", False)
        )

        # Fleet config
        _fleet = self._default_cfg.get("fleet", {})
        self._mqtt_broker: str = _fleet["mqtt_broker"]
        self._mqtt_port: int = int(_fleet["mqtt_port"])
        self._aws_iot_enabled: bool = bool(_fleet.get("aws_iot_enabled", False))

        # ZMQ connection — read host and port from config; subscribers connect to the
        # broker XPUB socket (see zmq_broker.py and bus.py Subscriber).
        _system = self._default_cfg.get("system", {})
        self._zmq_broker_host: str = str(_system.get("zmq_broker_host", "localhost"))
        self._zmq_subscriber_port: int = int(_system.get("zmq_subscriber_port", 5555))

        # Topic names from contracts
        self._subscribe_topic: str = self._find_topic_name("03_fusion_edge_platform")
        self._publish_topic: str = self._find_topic_name("04_hmi_alerts_fleet")

        # Runtime state
        self._vehicle_id: str = _get_or_create_vehicle_id()
        self._seq: int = 0

        # Event tracking (for duration calculation)
        self._event_start_ts: Optional[float] = None
        self._current_tier: int = 0

        # MQTT client (may be None if paho not installed)
        self._mqtt_client = self._init_mqtt()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_topic_name(self, publisher_prefix: str) -> str:
        """Return the topic name whose publisher starts with *publisher_prefix*.

        Scans ``contracts/topics.yaml`` topics list.

        Parameters
        ----------
        publisher_prefix:
            Prefix of the ``publisher`` field to match, e.g.
            ``"03_fusion_edge_platform"`` or ``"04_hmi_alerts_fleet"``.

        Returns
        -------
        str
            The matching topic string.

        Raises
        ------
        KeyError
            If no matching topic is found.
        """
        for entry in self._topics_cfg.get("topics", []):
            if entry.get("publisher", "").startswith(publisher_prefix):
                return entry["topic"]
        raise KeyError(
            f"No topic found for publisher prefix '{publisher_prefix}' "
            f"in contracts/topics.yaml"
        )

    def _init_mqtt(self):
        """Attempt to create a paho-mqtt client; return ``None`` on failure.

        Returns
        -------
        mqtt.Client or None
        """
        if self._aws_iot_enabled:
            logger.warning("AWS IoT not configured in this build — falling back to local MQTT.")

        try:
            import paho.mqtt.client as mqtt  # type: ignore
        except ImportError:
            warnings.warn(
                "paho-mqtt is not installed. Telemetry will be logged locally only. "
                "Install with: pip install paho-mqtt",
                ImportWarning,
                stacklevel=2,
            )
            return None

        client = mqtt.Client()
        try:
            client.connect(self._mqtt_broker, self._mqtt_port, keepalive=60)
            client.loop_start()
            logger.info(
                "MQTT connected to %s:%d", self._mqtt_broker, self._mqtt_port
            )
        except Exception as exc:  # broker may not be running in CI
            logger.warning("MQTT connect failed (%s). Will retry on publish.", exc)
        return client

    def _publish_event(self, event_type: str, tier: int, duration_s: float) -> None:
        """Build and dispatch a TelemetryEvent.

        Only fires when ``telemetry.opt_in_default`` is ``True``.

        Parameters
        ----------
        event_type:
            One of ``"drowsiness_event"`` or ``"recovery"``.
        tier:
            Drowsiness tier (0–3).
        duration_s:
            Duration of the event in seconds.
        """
        if not self._opt_in:
            return

        self._seq += 1
        payload: dict = {
            "ts": time.time() * 1000.0,  # epoch ms, matching schema
            "seq": self._seq,
            "vehicle_id": self._vehicle_id,
            "event_type": event_type,
            "tier": tier,
            "duration_s": round(duration_s, 3),
        }
        payload_str = json.dumps(payload)
        logger.info("TelemetryEvent: %s", payload_str)

        if self._mqtt_client is not None:
            try:
                self._mqtt_client.publish(
                    self._publish_topic, payload_str, qos=1
                )
            except Exception as exc:
                logger.warning("MQTT publish failed: %s", exc)

    def _handle_fusion_message(self, message: dict) -> None:
        """Process one FusionOutput message and emit telemetry if warranted.

        Parameters
        ----------
        message:
            Decoded FusionOutput dict (see ``contracts/schemas/FusionOutput.json``).
        """
        tier: int = int(message.get("level", 0))
        now: float = time.time()

        if tier > 0 and self._current_tier == 0:
            # Drowsiness event started
            self._event_start_ts = now
            self._current_tier = tier
        elif tier > 0 and self._current_tier > 0:
            # Still in event — update to highest tier seen
            self._current_tier = max(self._current_tier, tier)
        elif tier == 0 and self._current_tier > 0:
            # Recovery — event ended
            duration_s = (now - self._event_start_ts) if self._event_start_ts else 0.0
            self._publish_event("recovery", self._current_tier, duration_s)
            self._current_tier = 0
            self._event_start_ts = None
        # tier==0 and current==0 → nothing to do

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Subscribe to the fusion topic and begin forwarding telemetry.

        Blocks until interrupted.  If ``telemetry.opt_in_default`` is
        ``False`` the method returns immediately after logging a message.
        """
        if not self._opt_in:
            logger.info(
                "Telemetry opt-in is disabled (telemetry.opt_in_default=false). "
                "No data will be published. Enable via HMI consent dialog."
            )
            return

        try:
            import zmq  # type: ignore
        except ImportError:
            logger.error(
                "pyzmq is not installed. Cannot subscribe to fusion topic. "
                "Install with: pip install pyzmq"
            )
            return

        context = zmq.Context()
        socket = context.socket(zmq.SUB)

        # Derive ZMQ subscriber host and port from config/default.yaml
        # (system.zmq_broker_host and system.zmq_subscriber_port).
        # Subscribers connect to the broker's XPUB socket (see zmq_broker.py, bus.py Subscriber).
        socket.connect(f"tcp://{self._zmq_broker_host}:{self._zmq_subscriber_port}")
        socket.setsockopt_string(zmq.SUBSCRIBE, self._subscribe_topic)

        logger.info(
            "TelemetryPublisher subscribed to '%s' on %s:%d",
            self._subscribe_topic,
            self._zmq_broker_host,
            self._zmq_subscriber_port,
        )

        try:
            while True:
                try:
                    parts = socket.recv_multipart(flags=zmq.NOBLOCK)
                    if len(parts) >= 2:
                        raw = parts[1]
                        msg = json.loads(raw.decode())
                        self._handle_fusion_message(msg)
                except zmq.Again:
                    time.sleep(0.05)
        except KeyboardInterrupt:
            logger.info("TelemetryPublisher stopped by user.")
        finally:
            socket.close()
            context.term()
            if self._mqtt_client is not None:
                self._mqtt_client.loop_stop()
                self._mqtt_client.disconnect()

    def close(self) -> None:
        """Release MQTT resources.

        Safe to call even if the publisher was never started.
        """
        if self._mqtt_client is not None:
            try:
                self._mqtt_client.loop_stop()
                self._mqtt_client.disconnect()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    publisher = TelemetryPublisher()
    publisher.start()

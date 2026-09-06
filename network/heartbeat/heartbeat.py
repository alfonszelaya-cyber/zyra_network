"""
ZYRA Network liveness monitoring.

Heartbeat observation is intentionally separated from routing,
failover and consensus.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock
from time import monotonic


class HeartbeatState(str, Enum):
    UNKNOWN = "unknown"
    ALIVE = "alive"
    SUSPECT = "suspect"
    DEAD = "dead"


@dataclass(slots=True)
class Heartbeat:
    node_id: str
    interval_seconds: float
    timeout_seconds: float
    state: HeartbeatState = (
        HeartbeatState.UNKNOWN
    )
    last_received: float | None = None
    sequence: int = 0

    def __post_init__(self) -> None:
        self.node_id = self.node_id.strip()

        if not self.node_id:
            raise ValueError(
                "node_id cannot be empty"
            )

        if self.interval_seconds <= 0:
            raise ValueError(
                "interval_seconds must be positive"
            )

        if self.timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be positive"
            )

        if (
            self.timeout_seconds
            < self.interval_seconds
        ):
            raise ValueError(
                "timeout_seconds cannot be less "
                "than interval_seconds"
            )


class HeartbeatMonitor:
    """Thread-safe local heartbeat state machine."""

    def __init__(
        self,
        *,
        default_interval_seconds: float = 5.0,
        default_timeout_seconds: float = 15.0,
    ) -> None:

        if default_interval_seconds <= 0:
            raise ValueError(
                "default interval must be positive"
            )

        if (
            default_timeout_seconds
            < default_interval_seconds
        ):
            raise ValueError(
                "default timeout must be greater "
                "than or equal to interval"
            )

        self._default_interval = (
            default_interval_seconds
        )

        self._default_timeout = (
            default_timeout_seconds
        )

        self._heartbeats: dict[
            str,
            Heartbeat,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        node_id: str,
        *,
        interval_seconds: float | None = None,
        timeout_seconds: float | None = None,
    ) -> Heartbeat:

        heartbeat = Heartbeat(
            node_id=node_id,
            interval_seconds=(
                interval_seconds
                if interval_seconds is not None
                else self._default_interval
            ),
            timeout_seconds=(
                timeout_seconds
                if timeout_seconds is not None
                else self._default_timeout
            ),
        )

        with self._lock:
            if heartbeat.node_id in (
                self._heartbeats
            ):
                raise ValueError(
                    f"heartbeat already registered: "
                    f"{heartbeat.node_id}"
                )

            self._heartbeats[
                heartbeat.node_id
            ] = heartbeat

        return heartbeat

    def receive(
        self,
        node_id: str,
        sequence: int,
    ) -> Heartbeat:

        node_id = node_id.strip()

        if sequence < 0:
            raise ValueError(
                "heartbeat sequence cannot be negative"
            )

        with self._lock:
            heartbeat = self._heartbeats.get(
                node_id
            )

            if heartbeat is None:
                raise LookupError(
                    f"heartbeat not registered: "
                    f"{node_id}"
                )

            if sequence < heartbeat.sequence:
                raise ValueError(
                    "heartbeat sequence moved backwards"
                )

            heartbeat.sequence = sequence
            heartbeat.last_received = monotonic()
            heartbeat.state = (
                HeartbeatState.ALIVE
            )

            return heartbeat

    def evaluate(
        self,
        node_id: str,
        *,
        now: float | None = None,
    ) -> HeartbeatState:

        node_id = node_id.strip()

        current = (
            monotonic()
            if now is None
            else now
        )

        with self._lock:
            heartbeat = self._heartbeats.get(
                node_id
            )

            if heartbeat is None:
                raise LookupError(
                    f"heartbeat not registered: "
                    f"{node_id}"
                )

            if heartbeat.last_received is None:
                heartbeat.state = (
                    HeartbeatState.UNKNOWN
                )
                return heartbeat.state

            elapsed = (
                current
                - heartbeat.last_received
            )

            if (
                elapsed
                <= heartbeat.interval_seconds
            ):
                heartbeat.state = (
                    HeartbeatState.ALIVE
                )

            elif (
                elapsed
                <= heartbeat.timeout_seconds
            ):
                heartbeat.state = (
                    HeartbeatState.SUSPECT
                )

            else:
                heartbeat.state = (
                    HeartbeatState.DEAD
                )

            return heartbeat.state

    def state(
        self,
        node_id: str,
    ) -> HeartbeatState:

        node_id = node_id.strip()

        with self._lock:
            heartbeat = self._heartbeats.get(
                node_id
            )

            if heartbeat is None:
                raise LookupError(
                    f"heartbeat not registered: "
                    f"{node_id}"
                )

            return heartbeat.state

    def remove(
        self,
        node_id: str,
    ) -> bool:

        with self._lock:
            return (
                self._heartbeats.pop(
                    node_id.strip(),
                    None,
                )
                is not None
            )

    def snapshot(
        self,
    ) -> tuple[Heartbeat, ...]:

        with self._lock:
            return tuple(
                self._heartbeats.values()
            )


__all__ = [
    "HeartbeatState",
    "Heartbeat",
    "HeartbeatMonitor",
]

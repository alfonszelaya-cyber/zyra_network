"""
Production failover state management.

Failover decisions are explicit and auditable. This layer does
not silently mutate routing tables or perform network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from time import monotonic
from typing import Mapping


class FailoverState(str, Enum):
    PRIMARY = "primary"
    STANDBY = "standby"
    FAILED = "failed"
    PROMOTED = "promoted"
    DISABLED = "disabled"


class FailoverAction(str, Enum):
    PROMOTE = "promote"
    DEMOTE = "demote"
    MARK_FAILED = "mark_failed"
    RESTORE = "restore"


@dataclass(slots=True)
class FailoverTarget:
    target_id: str
    endpoint: str
    priority: int = 100
    state: FailoverState = FailoverState.STANDBY
    metadata: dict[str, str] = field(
        default_factory=dict
    )
    changed_at: float = field(
        default_factory=monotonic
    )

    def __post_init__(self) -> None:
        self.target_id = self.target_id.strip()
        self.endpoint = self.endpoint.strip()

        if not self.target_id:
            raise ValueError(
                "target_id cannot be empty"
            )

        if not self.endpoint:
            raise ValueError(
                "failover endpoint cannot be empty"
            )

        if self.priority < 0:
            raise ValueError(
                "priority cannot be negative"
            )


class FailoverManager:
    """Thread-safe failover target manager."""

    def __init__(self) -> None:
        self._targets: dict[
            str,
            FailoverTarget,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        target: FailoverTarget,
    ) -> None:

        if not isinstance(
            target,
            FailoverTarget,
        ):
            raise TypeError(
                "target must be FailoverTarget"
            )

        with self._lock:
            if target.target_id in self._targets:
                raise ValueError(
                    "failover target already exists: "
                    f"{target.target_id}"
                )

            self._targets[
                target.target_id
            ] = target

    def action(
        self,
        target_id: str,
        action: FailoverAction,
    ) -> FailoverTarget:

        if not isinstance(
            action,
            FailoverAction,
        ):
            raise TypeError(
                "action must be FailoverAction"
            )

        with self._lock:
            target = self._targets.get(
                target_id.strip()
            )

            if target is None:
                raise LookupError(
                    f"failover target not found: "
                    f"{target_id}"
                )

            if action is FailoverAction.PROMOTE:
                target.state = (
                    FailoverState.PROMOTED
                )

            elif action is FailoverAction.DEMOTE:
                target.state = (
                    FailoverState.STANDBY
                )

            elif action is FailoverAction.MARK_FAILED:
                target.state = (
                    FailoverState.FAILED
                )

            elif action is FailoverAction.RESTORE:
                target.state = (
                    FailoverState.STANDBY
                )

            target.changed_at = monotonic()

            return target

    def best_standby(
        self,
    ) -> FailoverTarget:

        with self._lock:
            candidates = tuple(
                target
                for target
                in self._targets.values()
                if target.state
                is FailoverState.STANDBY
            )

            if not candidates:
                raise LookupError(
                    "no standby failover target available"
                )

            return min(
                candidates,
                key=lambda item: (
                    item.priority,
                    item.target_id,
                ),
            )

    def active_target(
        self,
    ) -> FailoverTarget | None:

        with self._lock:
            promoted = tuple(
                target
                for target
                in self._targets.values()
                if target.state
                is FailoverState.PROMOTED
            )

            if not promoted:
                return None

            return min(
                promoted,
                key=lambda item: (
                    item.priority,
                    item.target_id,
                ),
            )

    def snapshot(
        self,
    ) -> tuple[FailoverTarget, ...]:

        with self._lock:
            return tuple(
                FailoverTarget(
                    target_id=item.target_id,
                    endpoint=item.endpoint,
                    priority=item.priority,
                    state=item.state,
                    metadata=dict(
                        item.metadata
                    ),
                    changed_at=item.changed_at,
                )
                for item
                in self._targets.values()
            )


__all__ = [
    "FailoverState",
    "FailoverAction",
    "FailoverTarget",
    "FailoverManager",
]

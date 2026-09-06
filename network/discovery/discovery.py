"""
ZYRA Network service discovery registry.

Discovery records service identity, endpoint and liveness.
Routing and load balancing consume discovery data later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from time import monotonic
from typing import Mapping


class DiscoveryStatus(str, Enum):
    REGISTERING = "registering"
    ACTIVE = "active"
    DEGRADED = "degraded"
    DRAINING = "draining"
    OFFLINE = "offline"


@dataclass(slots=True)
class DiscoveryRecord:
    service_id: str
    instance_id: str
    endpoint: str
    status: DiscoveryStatus = (
        DiscoveryStatus.REGISTERING
    )
    weight: int = 1
    metadata: dict[str, str] = field(
        default_factory=dict
    )
    registered_at: float = field(
        default_factory=monotonic
    )
    last_seen: float = field(
        default_factory=monotonic
    )

    def __post_init__(self) -> None:
        self.service_id = (
            self.service_id.strip()
        )

        self.instance_id = (
            self.instance_id.strip()
        )

        self.endpoint = (
            self.endpoint.strip()
        )

        if not self.service_id:
            raise ValueError(
                "service_id cannot be empty"
            )

        if not self.instance_id:
            raise ValueError(
                "instance_id cannot be empty"
            )

        if not self.endpoint:
            raise ValueError(
                "endpoint cannot be empty"
            )

        if self.weight <= 0:
            raise ValueError(
                "weight must be positive"
            )


class DiscoveryRegistry:
    """Thread-safe service discovery registry."""

    def __init__(self) -> None:
        self._records: dict[
            tuple[str, str],
            DiscoveryRecord,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        service_id: str,
        instance_id: str,
        endpoint: str,
        *,
        weight: int = 1,
        metadata: Mapping[str, str] | None = None,
    ) -> DiscoveryRecord:

        record = DiscoveryRecord(
            service_id=service_id,
            instance_id=instance_id,
            endpoint=endpoint,
            status=DiscoveryStatus.ACTIVE,
            weight=weight,
            metadata=dict(
                metadata or {}
            ),
        )

        key = (
            record.service_id,
            record.instance_id,
        )

        with self._lock:
            existing = self._records.get(
                key
            )

            if (
                existing is not None
                and existing.endpoint
                != record.endpoint
            ):
                raise ValueError(
                    "service instance already "
                    "registered with another endpoint"
                )

            self._records[key] = record

            return record

    def heartbeat(
        self,
        service_id: str,
        instance_id: str,
    ) -> None:

        key = (
            service_id.strip(),
            instance_id.strip(),
        )

        with self._lock:
            record = self._records.get(
                key
            )

            if record is None:
                raise LookupError(
                    f"service instance not found: "
                    f"{key}"
                )

            record.last_seen = monotonic()
            record.status = (
                DiscoveryStatus.ACTIVE
            )

    def set_status(
        self,
        service_id: str,
        instance_id: str,
        status: DiscoveryStatus,
    ) -> None:

        if not isinstance(
            status,
            DiscoveryStatus,
        ):
            raise TypeError(
                "status must be DiscoveryStatus"
            )

        key = (
            service_id.strip(),
            instance_id.strip(),
        )

        with self._lock:
            record = self._records.get(
                key
            )

            if record is None:
                raise LookupError(
                    f"service instance not found: "
                    f"{key}"
                )

            record.status = status

    def resolve(
        self,
        service_id: str,
    ) -> tuple[DiscoveryRecord, ...]:

        service_id = service_id.strip()

        with self._lock:
            return tuple(
                sorted(
                    (
                        record
                        for record
                        in self._records.values()
                        if (
                            record.service_id
                            == service_id
                            and record.status
                            in {
                                DiscoveryStatus.ACTIVE,
                                DiscoveryStatus.DEGRADED,
                            }
                        )
                    ),
                    key=lambda item: (
                        -item.weight,
                        item.instance_id,
                    ),
                )
            )

    def get(
        self,
        service_id: str,
        instance_id: str,
    ) -> DiscoveryRecord | None:

        key = (
            service_id.strip(),
            instance_id.strip(),
        )

        with self._lock:
            return self._records.get(key)

    def remove(
        self,
        service_id: str,
        instance_id: str,
    ) -> bool:

        key = (
            service_id.strip(),
            instance_id.strip(),
        )

        with self._lock:
            return (
                self._records.pop(
                    key,
                    None,
                )
                is not None
            )

    def snapshot(
        self,
    ) -> tuple[DiscoveryRecord, ...]:

        with self._lock:
            return tuple(
                self._records.values()
            )


__all__ = [
    "DiscoveryStatus",
    "DiscoveryRecord",
    "DiscoveryRegistry",
]

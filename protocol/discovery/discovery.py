from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class ServiceRecord:
    service_id: str
    endpoint: str
    version: str
    capabilities: frozenset[str]
    registered_at: datetime

    @classmethod
    def create(
        cls,
        service_id: str,
        endpoint: str,
        version: str,
        capabilities: set[str] | frozenset[str] = frozenset(),
    ) -> "ServiceRecord":
        if not service_id.strip():
            raise ValueError("service_id cannot be empty")
        if not endpoint.strip():
            raise ValueError("endpoint cannot be empty")
        if not version.strip():
            raise ValueError("version cannot be empty")

        return cls(
            service_id=service_id.strip(),
            endpoint=endpoint.strip(),
            version=version.strip(),
            capabilities=frozenset(
                item.strip()
                for item in capabilities
                if item.strip()
            ),
            registered_at=datetime.now(timezone.utc),
        )


class ServiceDiscovery:
    def __init__(self) -> None:
        self._records: dict[str, ServiceRecord] = {}

    def register(self, record: ServiceRecord) -> None:
        if record.service_id in self._records:
            raise ValueError(
                f"Service already registered: {record.service_id}"
            )
        self._records[record.service_id] = record

    def unregister(self, service_id: str) -> bool:
        return self._records.pop(service_id.strip(), None) is not None

    def get(self, service_id: str) -> ServiceRecord:
        return self._records[service_id.strip()]

    def find_by_capability(
        self,
        capability: str,
    ) -> tuple[ServiceRecord, ...]:
        capability = capability.strip()
        return tuple(
            record
            for record in self._records.values()
            if capability in record.capabilities
        )

    def all(self) -> tuple[ServiceRecord, ...]:
        return tuple(self._records.values())


__all__ = ["ServiceRecord", "ServiceDiscovery"]

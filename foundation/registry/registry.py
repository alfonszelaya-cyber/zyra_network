from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any


class RegistryError(RuntimeError):
    """Base registry exception."""


class RegistryAuthorizationError(RegistryError):
    """Raised when registry access is not authorized."""


class RegistryConflictError(RegistryError):
    """Raised when an immutable registration conflicts."""


class RegistryNotFoundError(RegistryError):
    """Raised when an entity is not registered."""


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    """
    Universal Network registry entry.

    The registry identifies and describes an entity. It does not
    replace the authoritative data owned by the responsible system.
    """

    entity_id: str
    entity_type: str
    source: str
    created_at: datetime
    updated_at: datetime
    version: int
    attributes: tuple[tuple[str, Any], ...]
    sources: tuple[str, ...]

    def attributes_dict(self) -> dict[str, Any]:
        return dict(self.attributes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "attributes": self.attributes_dict(),
            "sources": list(self.sources),
        }


class RegistryAccessPolicy:
    """
    Authorization boundary for registry operations.

    A caller must explicitly declare that it is authorized to
    perform the requested operation.
    """

    READ = "read"
    WRITE = "write"
    UPDATE = "update"
    DISCOVER = "discover"

    def __init__(self) -> None:
        self._permissions: dict[str, set[str]] = {}
        self._lock = RLock()

    def grant(
        self,
        principal: str,
        *operations: str,
    ) -> None:
        if not principal:
            raise ValueError(
                "principal cannot be empty"
            )

        allowed = {
            self.READ,
            self.WRITE,
            self.UPDATE,
            self.DISCOVER,
        }

        if any(
            operation not in allowed
            for operation in operations
        ):
            raise ValueError(
                "Unknown registry operation"
            )

        with self._lock:
            self._permissions.setdefault(
                principal,
                set(),
            ).update(operations)

    def revoke(
        self,
        principal: str,
        *operations: str,
    ) -> None:
        with self._lock:
            permissions = self._permissions.get(
                principal
            )

            if permissions is None:
                return

            permissions.difference_update(
                operations
            )

            if not permissions:
                self._permissions.pop(
                    principal,
                    None,
                )

    def check(
        self,
        principal: str,
        operation: str,
    ) -> None:
        with self._lock:
            permissions = self._permissions.get(
                principal,
                set(),
            )

            if operation not in permissions:
                raise RegistryAuthorizationError(
                    f"Principal '{principal}' is not "
                    f"authorized for '{operation}'"
                )


class Registry:
    """
    Thread-safe universal Network registry.

    It provides:
    - universal entity discovery
    - cross-application source tracking
    - controlled reads
    - controlled writes
    - controlled updates
    - deterministic entity lookup
    - versioned records
    - source federation

    The registry is deliberately independent from databases,
    HTTP servers and message brokers. Those integrations belong
    to higher Network layers.
    """

    def __init__(
        self,
        *,
        access_policy: RegistryAccessPolicy | None = None,
    ) -> None:
        self._entries: dict[
            str,
            RegistryEntry,
        ] = {}

        self._lock = RLock()

        self._policy = (
            access_policy
            or RegistryAccessPolicy()
        )

    @property
    def access_policy(
        self,
    ) -> RegistryAccessPolicy:
        return self._policy

    def register(
        self,
        *,
        principal: str,
        entity_id: str,
        entity_type: str,
        source: str,
        attributes: dict[str, Any] | None = None,
    ) -> RegistryEntry:
        self._policy.check(
            principal,
            RegistryAccessPolicy.WRITE,
        )

        self._validate_entity(
            entity_id,
            entity_type,
            source,
        )

        now = datetime.now(timezone.utc)

        with self._lock:
            existing = self._entries.get(
                entity_id
            )

            if existing is not None:
                raise RegistryConflictError(
                    f"Entity already registered: "
                    f"{entity_id}"
                )

            entry = RegistryEntry(
                entity_id=entity_id,
                entity_type=entity_type,
                source=source,
                created_at=now,
                updated_at=now,
                version=1,
                attributes=tuple(
                    sorted(
                        (attributes or {}).items(),
                        key=lambda item: item[0],
                    )
                ),
                sources=(source,),
            )

            self._entries[
                entity_id
            ] = entry

            return entry

    def upsert(
        self,
        *,
        principal: str,
        entity_id: str,
        entity_type: str,
        source: str,
        attributes: dict[str, Any] | None = None,
    ) -> RegistryEntry:
        self._policy.check(
            principal,
            RegistryAccessPolicy.WRITE,
        )

        self._validate_entity(
            entity_id,
            entity_type,
            source,
        )

        with self._lock:
            existing = self._entries.get(
                entity_id
            )

            if existing is None:
                now = datetime.now(
                    timezone.utc
                )

                entry = RegistryEntry(
                    entity_id=entity_id,
                    entity_type=entity_type,
                    source=source,
                    created_at=now,
                    updated_at=now,
                    version=1,
                    attributes=tuple(
                        sorted(
                            (
                                attributes or {}
                            ).items(),
                            key=lambda item: item[0],
                        )
                    ),
                    sources=(source,),
                )

                self._entries[
                    entity_id
                ] = entry

                return entry

            self._policy.check(
                principal,
                RegistryAccessPolicy.UPDATE,
            )

            merged = (
                existing.attributes_dict()
            )

            if attributes:
                merged.update(attributes)

            sources = set(
                existing.sources
            )

            sources.add(source)

            updated = RegistryEntry(
                entity_id=existing.entity_id,
                entity_type=existing.entity_type,
                source=existing.source,
                created_at=existing.created_at,
                updated_at=datetime.now(
                    timezone.utc
                ),
                version=existing.version + 1,
                attributes=tuple(
                    sorted(
                        merged.items(),
                        key=lambda item: item[0],
                    )
                ),
                sources=tuple(
                    sorted(sources)
                ),
            )

            self._entries[
                entity_id
            ] = updated

            return updated

    def resolve(
        self,
        *,
        principal: str,
        entity_id: str,
    ) -> RegistryEntry:
        self._policy.check(
            principal,
            RegistryAccessPolicy.READ,
        )

        with self._lock:
            entry = self._entries.get(
                entity_id
            )

            if entry is None:
                raise RegistryNotFoundError(
                    f"Entity not found: "
                    f"{entity_id}"
                )

            return entry

    def discover(
        self,
        *,
        principal: str,
        entity_type: str | None = None,
    ) -> tuple[RegistryEntry, ...]:
        self._policy.check(
            principal,
            RegistryAccessPolicy.DISCOVER,
        )

        with self._lock:
            entries = tuple(
                self._entries.values()
            )

        if entity_type is None:
            return tuple(
                sorted(
                    entries,
                    key=lambda item:
                        item.entity_id,
                )
            )

        return tuple(
            sorted(
                (
                    entry
                    for entry in entries
                    if entry.entity_type
                    == entity_type
                ),
                key=lambda item:
                    item.entity_id,
            )
        )

    def exists(
        self,
        *,
        principal: str,
        entity_id: str,
    ) -> bool:
        self._policy.check(
            principal,
            RegistryAccessPolicy.READ,
        )

        with self._lock:
            return entity_id in self._entries

    def count(self) -> int:
        with self._lock:
            return len(self._entries)

    def snapshot(
        self,
        *,
        principal: str,
    ) -> tuple[RegistryEntry, ...]:
        self._policy.check(
            principal,
            RegistryAccessPolicy.DISCOVER,
        )

        with self._lock:
            return tuple(
                sorted(
                    self._entries.values(),
                    key=lambda item:
                        item.entity_id,
                )
            )

    @staticmethod
    def _validate_entity(
        entity_id: str,
        entity_type: str,
        source: str,
    ) -> None:
        if not isinstance(
            entity_id,
            str,
        ) or not entity_id.strip():
            raise ValueError(
                "entity_id must be non-empty"
            )

        if not isinstance(
            entity_type,
            str,
        ) or not entity_type.strip():
            raise ValueError(
                "entity_type must be non-empty"
            )

        if not isinstance(
            source,
            str,
        ) or not source.strip():
            raise ValueError(
                "source must be non-empty"
            )

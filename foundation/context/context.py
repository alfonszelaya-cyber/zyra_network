from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping
from uuid import UUID

from foundation.ids import generate_id


@dataclass(frozen=True, slots=True)
class Context:
    """
    Immutable execution context.

    Carries identity, correlation, causation, tenant and request
    metadata across Network boundaries without coupling components
    to HTTP, databases or message brokers.
    """

    context_id: str
    correlation_id: str
    created_at: datetime
    actor_id: str | None = None
    tenant_id: str | None = None
    request_id: str | None = None
    parent_context_id: str | None = None
    metadata: Mapping[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.context_id:
            raise ValueError("context_id cannot be empty")

        if not self.correlation_id:
            raise ValueError(
                "correlation_id cannot be empty"
            )

        if self.created_at.tzinfo is None:
            raise ValueError(
                "created_at must be timezone-aware"
            )

        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata)),
        )

    @classmethod
    def create(
        cls,
        *,
        actor_id: str | None = None,
        tenant_id: str | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
        parent_context_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "Context":
        context_id = str(
            generate_id("context")
        )

        correlation = (
            correlation_id
            or str(generate_id("correlation"))
        )

        return cls(
            context_id=context_id,
            correlation_id=correlation,
            created_at=datetime.now(timezone.utc),
            actor_id=actor_id,
            tenant_id=tenant_id,
            request_id=request_id,
            parent_context_id=parent_context_id,
            metadata=metadata or {},
        )

    def child(
        self,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> "Context":
        merged = dict(self.metadata)

        if metadata:
            merged.update(metadata)

        return Context.create(
            actor_id=self.actor_id,
            tenant_id=self.tenant_id,
            request_id=self.request_id,
            correlation_id=self.correlation_id,
            parent_context_id=self.context_id,
            metadata=merged,
        )

    def with_metadata(
        self,
        **values: Any,
    ) -> "Context":
        merged = dict(self.metadata)
        merged.update(values)

        return Context(
            context_id=self.context_id,
            correlation_id=self.correlation_id,
            created_at=self.created_at,
            actor_id=self.actor_id,
            tenant_id=self.tenant_id,
            request_id=self.request_id,
            parent_context_id=self.parent_context_id,
            metadata=merged,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "correlation_id": self.correlation_id,
            "created_at": self.created_at.isoformat(),
            "actor_id": self.actor_id,
            "tenant_id": self.tenant_id,
            "request_id": self.request_id,
            "parent_context_id": self.parent_context_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "Context":
        if not isinstance(value, Mapping):
            raise TypeError(
                "Context data must be a mapping"
            )

        created_at = datetime.fromisoformat(
            str(value["created_at"])
        )

        return cls(
            context_id=str(value["context_id"]),
            correlation_id=str(
                value["correlation_id"]
            ),
            created_at=created_at,
            actor_id=value.get("actor_id"),
            tenant_id=value.get("tenant_id"),
            request_id=value.get("request_id"),
            parent_context_id=value.get(
                "parent_context_id"
            ),
            metadata=value.get("metadata", {}),
        )

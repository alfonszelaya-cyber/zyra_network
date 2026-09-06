from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ComponentMetadata:
    """Immutable metadata describing a network component."""

    name: str
    version: str
    component_type: str
    owner: str | None = None
    description: str | None = None
    capabilities: frozenset[str] = field(default_factory=frozenset)
    attributes: Mapping[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Metadata name cannot be empty")

        if not self.version.strip():
            raise ValueError("Metadata version cannot be empty")

        if not self.component_type.strip():
            raise ValueError("Metadata component_type cannot be empty")

        object.__setattr__(
            self,
            "capabilities",
            frozenset(
                capability.strip()
                for capability in self.capabilities
                if capability and capability.strip()
            ),
        )

        object.__setattr__(
            self,
            "attributes",
            dict(self.attributes),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "component_type": self.component_type,
            "owner": self.owner,
            "description": self.description,
            "capabilities": sorted(self.capabilities),
            "attributes": dict(self.attributes),
            "registered_at": self.registered_at.isoformat(),
        }


__all__ = ["ComponentMetadata"]

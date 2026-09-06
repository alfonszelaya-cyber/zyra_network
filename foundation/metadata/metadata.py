from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class Metadata:
    """
    Immutable metadata attached to Network components and records.
    """

    name: str
    component_type: str
    version: str
    created_at: datetime = field(
        default_factory=lambda:
            datetime.now(timezone.utc)
    )
    attributes: Mapping[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name cannot be empty")

        if not self.component_type.strip():
            raise ValueError(
                "component_type cannot be empty"
            )

        if not self.version.strip():
            raise ValueError(
                "version cannot be empty"
            )

        if self.created_at.tzinfo is None:
            raise ValueError(
                "created_at must be timezone-aware"
            )

        object.__setattr__(
            self,
            "attributes",
            MappingProxyType(
                dict(self.attributes)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "component_type": self.component_type,
            "version": self.version,
            "created_at":
                self.created_at.isoformat(),
            "attributes":
                dict(self.attributes),
        }

    def with_attribute(
        self,
        key: str,
        value: Any,
    ) -> "Metadata":
        updated = dict(self.attributes)
        updated[key] = value

        return Metadata(
            name=self.name,
            component_type=self.component_type,
            version=self.version,
            created_at=self.created_at,
            attributes=updated,
        )

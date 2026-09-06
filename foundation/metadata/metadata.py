from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping


class MetadataError(ValueError):
    """Raised when metadata is invalid."""


@dataclass(frozen=True, slots=True)
class Metadata:
    """
    Immutable metadata describing a Network component/entity.

    Metadata is descriptive only. It never becomes the
    authoritative source for identity, ownership or business data.
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
        if not isinstance(
            self.name,
            str,
        ) or not self.name.strip():
            raise MetadataError(
                "name cannot be empty"
            )

        if not isinstance(
            self.component_type,
            str,
        ) or not self.component_type.strip():
            raise MetadataError(
                "component_type cannot be empty"
            )

        if not isinstance(
            self.version,
            str,
        ) or not self.version.strip():
            raise MetadataError(
                "version cannot be empty"
            )

        if self.created_at.tzinfo is None:
            raise MetadataError(
                "created_at must be timezone-aware"
            )

        object.__setattr__(
            self,
            "attributes",
            MappingProxyType(
                dict(self.attributes)
            ),
        )

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        return self.attributes.get(
            key,
            default,
        )

    def with_attribute(
        self,
        key: str,
        value: Any,
    ) -> "Metadata":
        if not isinstance(
            key,
            str,
        ) or not key.strip():
            raise MetadataError(
                "attribute key cannot be empty"
            )

        updated = dict(self.attributes)
        updated[key] = value

        return Metadata(
            name=self.name,
            component_type=self.component_type,
            version=self.version,
            created_at=self.created_at,
            attributes=updated,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "component_type":
                self.component_type,
            "version": self.version,
            "created_at":
                self.created_at.isoformat(),
            "attributes":
                dict(self.attributes),
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "Metadata":
        if not isinstance(
            value,
            Mapping,
        ):
            raise MetadataError(
                "Metadata must be a mapping"
            )

        created_at = datetime.fromisoformat(
            str(value["created_at"])
        )

        return cls(
            name=str(value["name"]),
            component_type=str(
                value["component_type"]
            ),
            version=str(value["version"]),
            created_at=created_at,
            attributes=value.get(
                "attributes",
                {},
            ),
        )

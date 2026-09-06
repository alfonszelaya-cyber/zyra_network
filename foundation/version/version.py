from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True, slots=True)
class Version:
    """
    Semantic version representation.

    Supports stable ordering and explicit compatibility checks.
    """

    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        if min(
            self.major,
            self.minor,
            self.patch,
        ) < 0:
            raise ValueError(
                "Version components cannot be negative"
            )

    def __str__(self) -> str:
        return (
            f"{self.major}."
            f"{self.minor}."
            f"{self.patch}"
        )

    @classmethod
    def parse(cls, value: str) -> "Version":
        parts = value.strip().split(".")

        if len(parts) != 3:
            raise ValueError(
                "Version must be MAJOR.MINOR.PATCH"
            )

        try:
            numbers = tuple(
                int(part)
                for part in parts
            )
        except ValueError as exc:
            raise ValueError(
                "Version contains non-numeric components"
            ) from exc

        return cls(*numbers)

    def compatible_with(
        self,
        other: "Version",
    ) -> bool:
        return self.major == other.major


FOUNDATION_VERSION = Version(1, 0, 0)
NETWORK_VERSION = Version(1, 0, 0)
PROTOCOL_VERSION = Version(1, 0, 0)

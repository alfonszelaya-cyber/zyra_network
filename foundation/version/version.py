from __future__ import annotations

import re
from dataclasses import dataclass


_SEMVER = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)


@dataclass(frozen=True, order=True, slots=True)
class Version:
    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        if min(self.major, self.minor, self.patch) < 0:
            raise ValueError("Version components cannot be negative")

    @classmethod
    def parse(cls, value: str) -> "Version":
        match = _SEMVER.match(value.strip())

        if not match:
            raise ValueError(f"Invalid semantic version: {value}")

        return cls(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


NETWORK_VERSION = Version(1, 0, 0)

__all__ = ["Version", "NETWORK_VERSION"]

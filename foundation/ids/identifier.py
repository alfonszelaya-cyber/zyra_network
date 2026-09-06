from __future__ import annotations

from dataclasses import dataclass
import re
from uuid import UUID

_ID_RE = re.compile(
    r"^zyra_[a-z0-9][a-z0-9_-]{0,63}_"
    r"[0-9a-f]{32}$"
)


@dataclass(frozen=True, slots=True)
class Identifier:
    """
    Canonical ZYRA identifier.

    Format:
        zyra_<namespace>_<128-bit-hex-value>

    The identifier is immutable and safe to serialize as text.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("Identifier value must be a string")

        if not _ID_RE.fullmatch(self.value):
            raise ValueError(
                "Invalid ZYRA identifier format"
            )

    @property
    def namespace(self) -> str:
        parts = self.value.split("_", 2)
        return parts[1]

    @property
    def raw_uuid(self) -> UUID:
        return UUID(self.value.rsplit("_", 1)[1])

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"Identifier({self.value!r})"

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.value,
            "namespace": self.namespace,
        }

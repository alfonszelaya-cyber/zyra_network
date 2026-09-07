"""Page container."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from shared_engines.common.validation import require_int_range

ItemT = TypeVar("ItemT")


@dataclass(frozen=True)
class Page(Generic[ItemT]):
    items: tuple[ItemT, ...]
    offset: int
    limit: int
    total: int

    def __post_init__(self) -> None:
        require_int_range(self.offset, "offset", 0, 10**12)
        require_int_range(self.limit, "limit", 1, 10**6)
        require_int_range(self.total, "total", 0, 10**12)

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    @property
    def next_offset(self) -> int | None:
        if self.has_more:
            return self.offset + len(self.items)
        return None

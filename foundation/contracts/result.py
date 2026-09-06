from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Result(Generic[T]):
    """Explicit success/failure result."""

    success: bool
    value: T | None = None
    error: Exception | None = None

    def __post_init__(self) -> None:
        if self.success and self.error is not None:
            raise ValueError(
                "Successful Result cannot contain an error"
            )

        if not self.success and self.error is None:
            raise ValueError(
                "Failed Result must contain an error"
            )

    @classmethod
    def ok(cls, value: T | None = None) -> "Result[T]":
        return cls(success=True, value=value)

    @classmethod
    def fail(cls, error: Exception) -> "Result[T]":
        if not isinstance(error, Exception):
            raise TypeError("error must be an Exception")
        return cls(success=False, error=error)

    def unwrap(self) -> T:
        if not self.success:
            assert self.error is not None
            raise self.error

        return self.value  # type: ignore[return-value]

    def unwrap_or(self, default: T) -> T:
        if self.success:
            return self.value  # type: ignore[return-value]

        return default

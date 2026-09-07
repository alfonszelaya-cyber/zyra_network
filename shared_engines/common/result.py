"""Explicit success/failure container."""
from __future__ import annotations

from typing import Generic, TypeVar, cast

from shared_engines.common.errors import ConfigurationError, EngineError

ValueT = TypeVar("ValueT")


class Result(Generic[ValueT]):
    """Holds exactly one of value or error.

    Factories: ``Result.ok(v)``, ``Result.err(e)``.
    Predicate: ``result.is_ok``.
    """

    __slots__ = ("_value", "_error")

    def __init__(
        self, value: ValueT | None, error: EngineError | None
    ) -> None:
        if (value is None) == (error is None):
            raise ConfigurationError(
                "Result requires exactly one of value or error"
            )
        self._value = value
        self._error = error

    @classmethod
    def ok(cls, value: ValueT) -> "Result[ValueT]":
        return cls(value, None)

    @classmethod
    def err(cls, error: EngineError) -> "Result[ValueT]":
        return cls(None, error)

    @property
    def is_ok(self) -> bool:
        return self._error is None

    @property
    def value(self) -> ValueT:
        if self._error is not None:
            raise self._error
        return cast(ValueT, self._value)

    @property
    def error(self) -> EngineError | None:
        return self._error

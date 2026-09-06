from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Mapping


class StateError(RuntimeError):
    """Base state error."""


class StateConflictError(StateError):
    """Raised when an expected state version is stale."""


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    version: int
    values: Mapping[str, Any]
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "values": dict(self.values),
            "updated_at": self.updated_at.isoformat(),
        }


class StateStore:
    """
    Thread-safe in-memory state primitive.

    This is the authoritative state interface for a single
    process. Persistent/distributed state implementations must
    implement their own adapter above this foundation layer.
    """

    def __init__(
        self,
        initial: Mapping[str, Any] | None = None,
    ) -> None:
        self._values = dict(initial or {})
        self._version = 0
        self._updated_at = datetime.now(
            timezone.utc
        )
        self._lock = RLock()

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        self._validate_key(key)

        with self._lock:
            return self._values.get(
                key,
                default,
            )

    def require(self, key: str) -> Any:
        self._validate_key(key)

        with self._lock:
            if key not in self._values:
                raise StateError(
                    f"State key not found: {key}"
                )

            return self._values[key]

    def set(
        self,
        key: str,
        value: Any,
        *,
        expected_version: int | None = None,
    ) -> StateSnapshot:
        self._validate_key(key)

        with self._lock:
            self._check_version(
                expected_version
            )

            self._values[key] = value
            self._version += 1
            self._updated_at = datetime.now(
                timezone.utc
            )

            return self.snapshot()

    def update(
        self,
        values: Mapping[str, Any],
        *,
        expected_version: int | None = None,
    ) -> StateSnapshot:
        if not isinstance(values, Mapping):
            raise TypeError(
                "values must be a mapping"
            )

        for key in values:
            self._validate_key(key)

        with self._lock:
            self._check_version(
                expected_version
            )

            self._values.update(values)
            self._version += 1
            self._updated_at = datetime.now(
                timezone.utc
            )

            return self.snapshot()

    def delete(
        self,
        key: str,
        *,
        expected_version: int | None = None,
    ) -> StateSnapshot:
        self._validate_key(key)

        with self._lock:
            self._check_version(
                expected_version
            )

            self._values.pop(key, None)
            self._version += 1
            self._updated_at = datetime.now(
                timezone.utc
            )

            return self.snapshot()

    def snapshot(self) -> StateSnapshot:
        with self._lock:
            return StateSnapshot(
                version=self._version,
                values=dict(self._values),
                updated_at=self._updated_at,
            )

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    def clear(
        self,
        *,
        expected_version: int | None = None,
    ) -> StateSnapshot:
        with self._lock:
            self._check_version(
                expected_version
            )

            self._values.clear()
            self._version += 1
            self._updated_at = datetime.now(
                timezone.utc
            )

            return self.snapshot()

    def _check_version(
        self,
        expected_version: int | None,
    ) -> None:
        if (
            expected_version is not None
            and expected_version != self._version
        ):
            raise StateConflictError(
                "State version conflict: "
                f"expected={expected_version}, "
                f"actual={self._version}"
            )

    @staticmethod
    def _validate_key(key: str) -> None:
        if (
            not isinstance(key, str)
            or not key.strip()
        ):
            raise ValueError(
                "State key cannot be empty"
            )

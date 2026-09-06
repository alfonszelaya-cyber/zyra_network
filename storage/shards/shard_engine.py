from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any


@dataclass(frozen=True, slots=True)
class ShardValue:
    key: str
    value: Any
    version: int


class ShardEngine:
    def __init__(self) -> None:
        self._data: dict[
            int,
            dict[str, ShardValue],
        ] = {}

        self._lock = RLock()

    def put(
        self,
        shard_id: int,
        key: str,
        value: Any,
    ) -> ShardValue:

        normalized = key.strip()

        if not normalized:
            raise ValueError(
                "Shard key cannot be empty"
            )

        with self._lock:
            shard = self._data.setdefault(
                shard_id,
                {},
            )

            previous = shard.get(
                normalized
            )

            version = (
                previous.version + 1
                if previous
                else 1
            )

            stored = ShardValue(
                key=normalized,
                value=value,
                version=version,
            )

            shard[
                normalized
            ] = stored

            return stored

    def get(
        self,
        shard_id: int,
        key: str,
    ) -> ShardValue:

        with self._lock:
            try:
                return self._data[
                    shard_id
                ][key.strip()]
            except KeyError as exc:
                raise LookupError(
                    f"Shard value not found: "
                    f"{shard_id}/{key}"
                ) from exc

    def delete(
        self,
        shard_id: int,
        key: str,
    ) -> bool:

        with self._lock:
            shard = self._data.get(
                shard_id
            )

            if not shard:
                return False

            return (
                shard.pop(
                    key.strip(),
                    None,
                )
                is not None
            )

    def keys(
        self,
        shard_id: int,
    ) -> tuple[str, ...]:

        with self._lock:
            return tuple(
                sorted(
                    self._data.get(
                        shard_id,
                        {},
                    )
                )
            )


__all__ = [
    "ShardEngine",
    "ShardValue",
]

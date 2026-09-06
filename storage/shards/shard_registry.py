from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class Shard:
    shard_id: int
    name: str
    capacity_bytes: int
    active: bool = True

    def __post_init__(self) -> None:
        if self.shard_id < 0:
            raise ValueError(
                "shard_id cannot be negative"
            )

        if not self.name.strip():
            raise ValueError(
                "Shard name cannot be empty"
            )

        if self.capacity_bytes <= 0:
            raise ValueError(
                "Shard capacity must be positive"
            )


class ShardRegistry:
    def __init__(self) -> None:
        self._shards: dict[
            int,
            Shard,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        shard: Shard,
        *,
        replace: bool = False,
    ) -> None:

        with self._lock:
            if (
                shard.shard_id in self._shards
                and not replace
            ):
                raise ValueError(
                    f"Shard already exists: "
                    f"{shard.shard_id}"
                )

            self._shards[
                shard.shard_id
            ] = shard

    def get(
        self,
        shard_id: int,
    ) -> Shard:

        with self._lock:
            try:
                return self._shards[
                    shard_id
                ]
            except KeyError as exc:
                raise LookupError(
                    f"Shard not found: {shard_id}"
                ) from exc

    def list(
        self,
    ) -> tuple[Shard, ...]:

        with self._lock:
            return tuple(
                self._shards[key]
                for key in sorted(
                    self._shards
                )
            )


__all__ = [
    "Shard",
    "ShardRegistry",
]

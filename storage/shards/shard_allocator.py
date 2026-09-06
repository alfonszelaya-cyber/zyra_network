from __future__ import annotations

import hashlib


class ShardAllocator:
    def __init__(
        self,
        shard_count: int,
    ) -> None:

        if shard_count <= 0:
            raise ValueError(
                "shard_count must be positive"
            )

        self.shard_count = shard_count

    def allocate(
        self,
        key: str,
    ) -> int:

        normalized = key.strip()

        if not normalized:
            raise ValueError(
                "Shard key cannot be empty"
            )

        digest = hashlib.sha256(
            normalized.encode(
                "utf-8"
            )
        ).digest()

        value = int.from_bytes(
            digest[:8],
            "big",
        )

        return value % self.shard_count


__all__ = ["ShardAllocator"]

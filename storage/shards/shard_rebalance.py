from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RebalancePlan:
    source_shard: int
    target_shard: int
    keys: tuple[str, ...]


class ShardRebalancer:
    def plan(
        self,
        source_shard: int,
        target_shard: int,
        keys: tuple[str, ...],
    ) -> RebalancePlan:

        if (
            source_shard
            == target_shard
        ):
            raise ValueError(
                "Source and target shards must differ"
            )

        return RebalancePlan(
            source_shard=source_shard,
            target_shard=target_shard,
            keys=tuple(
                sorted(set(keys))
            ),
        )


__all__ = [
    "RebalancePlan",
    "ShardRebalancer",
]

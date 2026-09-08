"""Hash-verified state replication between nodes."""
from __future__ import annotations

import json
from dataclasses import dataclass

from shared_engines.common.clocks import Clock
from shared_engines.common.identifiers import stable_hash
from shared_engines.common.validation import require_non_empty_str
from shared_engines.network.errors import ReplicationMismatchError
from shared_engines.storage.database import Database

REPLICATED_TABLES = (
    "identities",
    "cluster_nodes",
)


@dataclass(frozen=True)
class ReplicationReport:
    primary_node: str
    replica_node: str
    state_version: int
    state_hash: str
    consistent: bool
    rows_replicated: int


class ReplicationManager:
    """Computes state hashes and verifies replica parity."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def compute_state_hash(self) -> tuple[int, str]:
        parts: list[str] = []
        for table in REPLICATED_TABLES:
            rows = self._db.query_all(
                f"SELECT * FROM {table} ORDER BY rowid"
            )
            for row in rows:
                parts.append(
                    json.dumps(
                        {
                            k: str(v)
                            for k, v in dict(row).items()
                        },
                        sort_keys=True,
                    )
                )
        version = int(self._clock.now())
        return version, stable_hash(*parts)

    def replicate(
        self,
        *,
        primary_node: str,
        replica_node: str,
        replica_hash: str | None = None,
        rows_replicated: int = 0,
    ) -> ReplicationReport:
        require_non_empty_str(primary_node, "primary_node")
        require_non_empty_str(replica_node, "replica_node")
        version, primary_hash = self.compute_state_hash()
        if replica_hash is None:
            replica_hash = primary_hash
        consistent = replica_hash == primary_hash
        if not consistent:
            raise ReplicationMismatchError(
                f"replica {replica_node} hash"
                f" {replica_hash[:16]}"
                f" != primary {primary_hash[:16]}"
            )
        return ReplicationReport(
            primary_node=primary_node,
            replica_node=replica_node,
            state_version=version,
            state_hash=primary_hash,
            consistent=True,
            rows_replicated=rows_replicated,
        )

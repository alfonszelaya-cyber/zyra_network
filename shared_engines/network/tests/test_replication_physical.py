"""Physical replication proofs: rows really move
between two databases, deletes propagate, and
divergence is detected and healed."""
from __future__ import annotations

from pathlib import Path

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.events.contracts import (
    EventCatalog,
)
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import (
    IdentityKind,
)
from shared_engines.identity.engine import (
    IdentityEngine,
)
from shared_engines.network.cluster import (
    ClusterManager,
)
from shared_engines.network.replication import (
    ReplicationManager,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)


class _Node:
    """Real node: identity + cluster + replication."""

    def __init__(
        self, tmp_path: Path, name: str
    ) -> None:
        self.db = SQLiteAdapter(
            tmp_path / f"{name}.db"
        )
        self.clock = FrozenClock()
        self.audit = AuditTrail(
            self.db, self.clock
        )
        self.outbox = Outbox(
            self.db, self.clock
        )
        self.outbox.ensure_schema()
        self.catalog = EventCatalog()
        for et in (
            "identity.registered",
            "identity.status_changed",
            "network.node.joined",
            "network.node.state_changed",
        ):
            self.catalog.register(et)
        self.identity = IdentityEngine(
            db=self.db,
            clock=self.clock,
            audit=self.audit,
            outbox=self.outbox,
            catalog=self.catalog,
        )
        self.cluster = ClusterManager(
            db=self.db,
            clock=self.clock,
            audit=self.audit,
            outbox=self.outbox,
            catalog=self.catalog,
            heartbeat_ttl_seconds=30.0,
        )
        self.replication = ReplicationManager(
            self.db, self.clock
        )

    def close(self) -> None:
        self.db.close()


def _identity_count(
    node: _Node,
) -> int:
    row = node.db.query_one(
        "SELECT COUNT(*) AS n FROM identities"
    )
    assert row is not None
    return int(row["n"])


def test_transfer_resync_hashes_equal(
    tmp_path: Path,
) -> None:
    primary = _Node(tmp_path, "primary")
    replica = _Node(tmp_path, "replica")
    try:
        primary.identity.register_identity(
            kind=IdentityKind.PERSON,
            display_name="u1",
            actor="t",
        )
        report = (
            primary.replication.replicate_to(
                replica_db=replica.db,
                primary_node="A",
                replica_node="B",
            )
        )
        assert report.consistent is True
        assert report.rows_replicated >= 1
        assert (
            _identity_count(replica) == 1
        )
        _, hp = (
            primary.replication.compute_state_hash()
        )
        _, hr = (
            replica.replication.compute_state_hash()
        )
        assert hp == hr
        # Re-sync after new writes
        primary.identity.register_identity(
            kind=IdentityKind.PERSON,
            display_name="u2",
            actor="t",
        )
        primary.replication.replicate_to(
            replica_db=replica.db,
            primary_node="A",
            replica_node="B",
        )
        assert (
            _identity_count(replica) == 2
        )
        _, hp2 = (
            primary.replication.compute_state_hash()
        )
        _, hr2 = (
            replica.replication.compute_state_hash()
        )
        assert hp2 == hr2
    finally:
        primary.close()
        replica.close()


def test_delete_propagates_to_replica(
    tmp_path: Path,
) -> None:
    primary = _Node(tmp_path, "primary")
    replica = _Node(tmp_path, "replica")
    try:
        primary.identity.register_identity(
            kind=IdentityKind.PERSON,
            display_name="u1",
            actor="t",
        )
        primary.identity.register_identity(
            kind=IdentityKind.PERSON,
            display_name="u2",
            actor="t",
        )
        primary.replication.replicate_to(
            replica_db=replica.db,
            primary_node="A",
            replica_node="B",
        )
        assert (
            _identity_count(replica) == 2
        )
        primary.db.execute(
            "DELETE FROM identities WHERE"
            " rowid = (SELECT MIN(rowid)"
            " FROM identities)"
        )
        primary.replication.replicate_to(
            replica_db=replica.db,
            primary_node="A",
            replica_node="B",
        )
        assert (
            _identity_count(replica) == 1
        )
        _, hp = (
            primary.replication.compute_state_hash()
        )
        _, hr = (
            replica.replication.compute_state_hash()
        )
        assert hp == hr
    finally:
        primary.close()
        replica.close()


def test_divergence_detected_and_healed(
    tmp_path: Path,
) -> None:
    primary = _Node(tmp_path, "primary")
    replica = _Node(tmp_path, "replica")
    try:
        primary.identity.register_identity(
            kind=IdentityKind.PERSON,
            display_name="u1",
            actor="t",
        )
        primary.replication.replicate_to(
            replica_db=replica.db,
            primary_node="A",
            replica_node="B",
        )
        _, hp = (
            primary.replication.compute_state_hash()
        )
        _, hr = (
            replica.replication.compute_state_hash()
        )
        assert hp == hr
        # Tamper with the replica directly
        replica.db.execute(
            "UPDATE identities SET"
            " display_name = 'tampered'"
        )
        _, hr_bad = (
            replica.replication.compute_state_hash()
        )
        assert hr_bad != hp
        # Re-replication heals the divergence
        primary.replication.replicate_to(
            replica_db=replica.db,
            primary_node="A",
            replica_node="B",
        )
        _, hr_fixed = (
            replica.replication.compute_state_hash()
        )
        assert hr_fixed == hp
    finally:
        primary.close()
        replica.close()

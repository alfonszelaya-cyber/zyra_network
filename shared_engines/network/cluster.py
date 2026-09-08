"""Cluster membership: heartbeats drive the full lifecycle.

JOINING -> (heartbeat) -> ACTIVE -> SUSPECT -> DOWN ->
(heartbeat) -> REJOINED -> (heartbeat) -> ACTIVE.
A DOWN node that heartbeats again has clearly returned:
first beat marks it REJOINED, second confirms ACTIVE.
Cluster events go to the outbox transactionally and are
audited.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import Enum

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.errors import IntegrityError
from shared_engines.common.validation import (
    require_non_empty_str,
    require_positive_number,
)
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.network.errors import (
    InvalidTransitionError,
    NodeNotFoundError,
)
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

EVENT_NODE_JOINED = "network.node.joined"
EVENT_NODE_STATE_CHANGED = "network.node.state_changed"

CLUSTER_MIGRATIONS = (
    Migration(
        1,
        "cluster_nodes",
        (
            "CREATE TABLE cluster_nodes ("
            " node_id TEXT PRIMARY KEY,"
            " role TEXT NOT NULL,"
            " state TEXT NOT NULL,"
            " endpoint TEXT NOT NULL,"
            " joined_at REAL NOT NULL,"
            " last_heartbeat REAL NOT NULL,"
            " contract_version INTEGER NOT NULL)",
            "CREATE INDEX cluster_nodes_state"
            " ON cluster_nodes (state)",
        ),
    ),
)


class NodeRole(Enum):
    COORDINATOR = "coordinator"
    WORKER = "worker"
    REPLICA = "replica"


class NodeState(Enum):
    JOINING = "JOINING"
    ACTIVE = "ACTIVE"
    SUSPECT = "SUSPECT"
    DOWN = "DOWN"
    REJOINED = "REJOINED"


VALID_NODE_TRANSITIONS: dict[
    NodeState, frozenset[NodeState]
] = {
    NodeState.JOINING: frozenset(
        {NodeState.ACTIVE, NodeState.DOWN}
    ),
    NodeState.ACTIVE: frozenset(
        {NodeState.SUSPECT, NodeState.DOWN}
    ),
    NodeState.SUSPECT: frozenset(
        {NodeState.DOWN, NodeState.REJOINED}
    ),
    NodeState.DOWN: frozenset({NodeState.REJOINED}),
    NodeState.REJOINED: frozenset(
        {NodeState.ACTIVE, NodeState.SUSPECT, NodeState.DOWN}
    ),
}


@dataclass(frozen=True)
class NodeStatus:
    node_id: str
    role: NodeRole
    state: NodeState
    endpoint: str
    joined_at: float
    last_heartbeat: float


class ClusterManager:
    """Membership authority: register, heartbeat, detect."""

    def __init__(
        self,
        *,
        db: Database,
        clock: Clock,
        audit: AuditTrail,
        outbox: Outbox,
        catalog: EventCatalog,
        heartbeat_ttl_seconds: float = 30.0,
    ) -> None:
        require_positive_number(
            heartbeat_ttl_seconds,
            "heartbeat_ttl_seconds",
            config=True,
        )
        self._db = db
        self._clock = clock
        self._audit = audit
        self._outbox = outbox
        self._catalog = catalog
        self._ttl = heartbeat_ttl_seconds
        for event_type in (
            EVENT_NODE_JOINED,
            EVENT_NODE_STATE_CHANGED,
        ):
            self._catalog.register(event_type)
        MigrationRunner(
            db, "network.cluster", CLUSTER_MIGRATIONS
        ).run(clock)

    def register_node(
        self,
        *,
        node_id: str,
        role: NodeRole,
        endpoint: str,
    ) -> NodeStatus:
        require_non_empty_str(node_id, "node_id")
        require_non_empty_str(endpoint, "endpoint")
        now = self._clock.now()
        try:
            with self._db.transaction() as cursor:
                cursor.execute(
                    "INSERT INTO cluster_nodes"
                    " (node_id, role, state, endpoint,"
                    "  joined_at, last_heartbeat,"
                    "  contract_version)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        node_id,
                        role.value,
                        NodeState.JOINING.value,
                        endpoint,
                        now,
                        now,
                        1,
                    ),
                )
                event = self._catalog.build(
                    EVENT_NODE_JOINED,
                    aggregate_id=node_id,
                    payload={
                        "role": role.value,
                        "endpoint": endpoint,
                    },
                    clock=self._clock,
                )
                self._outbox.enqueue_in_transaction(
                    cursor, event
                )
        except sqlite3.IntegrityError as exc:
            raise InvalidTransitionError(
                f"node already registered: {node_id}"
            ) from exc
        self._audit.append(
            event_type=EVENT_NODE_JOINED,
            actor=node_id,
            subject=node_id,
            payload={"role": role.value, "endpoint": endpoint},
        )
        node = self.get(node_id)
        if node is None:
            raise IntegrityError("node vanished after insert")
        return node

    def heartbeat(self, node_id: str) -> None:
        """Refreshes liveness and advances the lifecycle:
        JOINING -> ACTIVE, SUSPECT -> ACTIVE,
        DOWN -> REJOINED (next beat confirms ACTIVE)."""
        require_non_empty_str(node_id, "node_id")
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE cluster_nodes"
                " SET last_heartbeat = ?,"
                " state = CASE state"
                "  WHEN 'JOINING' THEN 'ACTIVE'"
                "  WHEN 'SUSPECT' THEN 'ACTIVE'"
                "  WHEN 'REJOINED' THEN 'ACTIVE'"
                "  WHEN 'DOWN' THEN 'REJOINED'"
                "  ELSE state END"
                " WHERE node_id = ?",
                (now, node_id),
            )
            if cursor.rowcount != 1:
                raise NodeNotFoundError(
                    f"unknown node: {node_id}"
                )

    def get(self, node_id: str) -> NodeStatus | None:
        row = self._db.query_one(
            "SELECT * FROM cluster_nodes WHERE node_id = ?",
            (node_id,),
        )
        if row is None:
            return None
        return self._node_from_row(row)

    def require(self, node_id: str) -> NodeStatus:
        node = self.get(node_id)
        if node is None:
            raise NodeNotFoundError(
                f"unknown node: {node_id}"
            )
        return node

    def detect_failures(self) -> tuple[str, ...]:
        """ACTIVE->SUSPECT after TTL, SUSPECT->DOWN after 2x."""
        now = self._clock.now()
        changed: list[str] = []
        rows = self._db.query_all(
            "SELECT node_id, state, last_heartbeat"
            " FROM cluster_nodes WHERE state IN"
            " ('ACTIVE', 'SUSPECT')"
        )
        for row in rows:
            node_id = str(row["node_id"])
            state = NodeState(str(row["state"]))
            last = float(row["last_heartbeat"])
            age = now - last
            if state is NodeState.ACTIVE and age > self._ttl:
                self._transition(node_id, NodeState.SUSPECT)
                changed.append(node_id)
            elif (
                state is NodeState.SUSPECT
                and age > 2 * self._ttl
            ):
                self._transition(node_id, NodeState.DOWN)
                changed.append(node_id)
        return tuple(changed)

    def _transition(
        self, node_id: str, to_state: NodeState
    ) -> None:
        with self._db.transaction() as cursor:
            row = cursor.execute(
                "SELECT state FROM cluster_nodes"
                " WHERE node_id = ?",
                (node_id,),
            ).fetchone()
            if row is None:
                raise NodeNotFoundError(
                    f"unknown node: {node_id}"
                )
            current = NodeState(str(row["state"]))
            allowed = VALID_NODE_TRANSITIONS.get(
                current, frozenset()
            )
            if to_state not in allowed:
                raise InvalidTransitionError(
                    f"{current.value} -> {to_state.value}"
                )
            cursor.execute(
                "UPDATE cluster_nodes SET state = ?"
                " WHERE node_id = ?",
                (to_state.value, node_id),
            )
            event = self._catalog.build(
                EVENT_NODE_STATE_CHANGED,
                aggregate_id=node_id,
                payload={"to": to_state.value},
                clock=self._clock,
            )
            self._outbox.enqueue_in_transaction(cursor, event)
        self._audit.append(
            event_type=EVENT_NODE_STATE_CHANGED,
            actor="cluster-manager",
            subject=node_id,
            payload={"to": to_state.value},
        )

    def active_nodes(self) -> tuple[NodeStatus, ...]:
        rows = self._db.query_all(
            "SELECT * FROM cluster_nodes"
            " WHERE state IN ('ACTIVE', 'REJOINED')"
            " ORDER BY node_id"
        )
        return tuple(self._node_from_row(r) for r in rows)

    def all_nodes(self) -> tuple[NodeStatus, ...]:
        rows = self._db.query_all(
            "SELECT * FROM cluster_nodes ORDER BY node_id"
        )
        return tuple(self._node_from_row(r) for r in rows)

    @staticmethod
    def _node_from_row(row: sqlite3.Row) -> NodeStatus:
        return NodeStatus(
            node_id=str(row["node_id"]),
            role=NodeRole(str(row["role"])),
            state=NodeState(str(row["state"])),
            endpoint=str(row["endpoint"]),
            joined_at=float(row["joined_at"]),
            last_heartbeat=float(row["last_heartbeat"]),
        )

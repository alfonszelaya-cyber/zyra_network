# Architecture Decisions

Durable record of structural decisions, so future
audits do not re-open settled questions.

## ADR-001: no standalone node_runtime.py

**Decision:** not to create
`shared_engines/network/node_runtime.py`.

**Rationale:** `CONTRACTS.md` declares
`shared_engines/network/cluster.py`,
`failover.py` and `replication.py` as the
canonical authorities; `ZyraKernel` and
`ZyraCapabilities` are the composition roots.
A separate node runtime would duplicate semantics
already canonical. If a clearly separable
responsibility emerges (e.g. long-lived process
supervision per node), this decision is revisited.

**Status:** accepted (W20b).

## ADR-002: root facades are re-exports, not engines

**Decision:** root packages `telemetry/` and
`observability/` are facades over the real engines
in `shared_engines/`.

**Rationale:** the audit required no decorative
duplicate implementations. `telemetry/__init__.py`
re-exports the engine API (W20a);
`observability/__init__.py` already was a real
facade over its `core.py` and submodules
(confirmed in W20b review) and is left as-is.

**Status:** accepted (W20a/W20b).

## ADR-003: operational scripts share one pattern

**Decision:** every script in `scripts/` exposes
`run(**kwargs) -> int`, uses argparse + `main()`
in `__main__`, prints operational results, and
reuses engines (migrations, snapshots, integrity)
instead of reimplementing them.

**Status:** accepted (W20b):
`install.py`, `deploy.py`, `repair.py`,
`update.py` join the existing
`backup/bootstrap/cleanup/diagnostics/migrate/
rollback/verify_installation` set.

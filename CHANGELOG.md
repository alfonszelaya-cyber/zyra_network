# Changelog

All notable construction phases of ZYRA Network.
Each entry landed as a green CI run with tested code.

## [1.0.0] - Network Core Complete

### Added
- W1 Network flow: failover publishes elected events to the
  outbox; failover -> audit -> outbox -> telemetry closes.
- W2 Storage lifecycle: typed DatabaseClosedError, adapter
  self-heal reopen on restored-file inode swap, fsync-durable
  snapshot restore.
- W3 Outbox concurrency: atomic claim/lease, fencing tokens
  (LeaseLost), exponential backoff retry, dead-letter +
  requeue, expired-lease reaper.
- W4 Physical replication: export_state/apply_state with
  FK-safe apply, transfer -> apply -> verify -> ack, delete
  propagation, divergence heal.

### Added - Trust services (product core)
- W5 Portable identity: ProfileRegistry with per-field
  verification levels and scoped cross-app access, audited.
- W6 Trust flow: onboarding walk REGISTERED ->
  PENDING_VERIFICATION -> VERIFIED -> ACTIVE via the identity
  contract; evidence-backed is_trusted.
- W7 Lifelong history: append-only per-ZID civic timeline
  (birth_registration first), tamper-evident hash chain.

### Added - 17 transverse engines
- consensus, integrity, encryption (durable keyring over
  EnvelopeCrypto), certification (accredited issuers, cascade
  revocation), search (authorized + audited), reputation
  (evidence-backed, decay), compression (bomb guards),
  scalability (backpressure + stable partitioning),
  supervisor (restart budget -> quarantine), workflow
  (saga compensation), routing (prioritized failover),
  system_loader (manifest compatibility policy), compliance
  (multi-jurisdiction), integrations (retry/health), export
  (signed offline-verifiable bundles), interoperability
  (mutual-version negotiation), ai (honest provenance).

### Added - Composition and surface
- W18 Structural cleanup: 26 orphan __init__py dirs removed,
  empty namespaces removed; ZyraCapabilities composes 14
  trust services over one database.
- W19 HTTP trust surface: CapabilitiesApiHandler +
  CapabilitiesServer (14 routes), optional bearer token,
  registered-apps enforced by engines.
- W20a Audit-gap closure: pytest normal collection fixed
  (all test basenames unique), README/CHANGELOG written,
  root authority rotation runbook, telemetry root facade.

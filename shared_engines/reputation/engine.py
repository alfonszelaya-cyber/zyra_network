"""Reputation engine: evidence -> score, nothing
else.

Flow per event:

    actor (another ZID, never self)
          |
          v
    evidence bytes (real content)
          |
          v
    IntegrityEngine.issue_proof
    (durable, verifiable SHA-256)
          |
          v
    reputation_events append-only row
    (seq per subject, evidence_sha, proof_id)
          |
          v
    score = sum(sign * weight
                * decay(age))
    (policy-driven, transparent)

Guarantees:

- No self-rating: actor != subject, both must
  be known identities.
- Evidence inmutable: every event carries a
  verifiable integrity proof id; the evidence
  hash is stored, so tampering with history
  is detectable by recomputing.
- Deterministic score: pure function of the
  event list, the policy and the clock.
- Every event is audited and emitted as
  reputation.event.recorded.

Deliberately separate from TokenLedger: tokens
are spendable currency; reputation is earned
trust with evidence and time decay.
"""
from __future__ import annotations

import hashlib
import sqlite3

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.errors import (
    NotFoundError,
)
from shared_engines.common.identifiers import (
    new_id,
)
from shared_engines.common.serialization import (
    canonical_json_dumps,
)
from shared_engines.common.validation import (
    require_non_empty_str,
)
from shared_engines.events.outbox import Outbox
from shared_engines.identity.engine import (
    IdentityEngine,
)
from shared_engines.integrity.engine import (
    IntegrityEngine,
)
from shared_engines.reputation.contracts import (
    EVENT_KINDS,
    KIND_NEGATIVE,
    KIND_POSITIVE,
    ReputationEvent,
    ReputationSummary,
)
from shared_engines.reputation.errors import (
    EmptyEvidenceError,
    SelfReputationError,
    UnknownEntityError,
)
from shared_engines.reputation.policy import (
    ReputationPolicy,
)
from shared_engines.storage.database import (
    Database,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

EVENT_RECORDED = (
    "reputation.event.recorded"
)

_MIGRATIONS = (
    Migration(
        1,
        "reputation_events",
        (
            "CREATE TABLE"
            " reputation_events ("
            " event_id TEXT PRIMARY KEY,"
            " seq INTEGER NOT NULL,"
            " subject_zid TEXT NOT NULL,"
            " actor_zid TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " weight REAL NOT NULL,"
            " evidence_sha TEXT NOT NULL,"
            " proof_id TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE INDEX rep_subject"
            " ON reputation_events"
            " (subject_zid, seq)",
        ),
    ),
)


class ReputationEngine:
    """Evidence-backed trust scoring."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        identity: IdentityEngine,
        integrity: IntegrityEngine,
        audit: AuditTrail,
        outbox: Outbox,
        policy: ReputationPolicy
        | None = None,
    ) -> None:
        self._db = db
        self._clock = clock
        self._identity = identity
        self._integrity = integrity
        self._audit = audit
        self._outbox = outbox
        self._policy = (
            policy or ReputationPolicy()
        )
        MigrationRunner(
            db,
            "reputation",
            _MIGRATIONS,
        ).run(clock)

    def _emit(
        self,
        cursor: sqlite3.Cursor,
        *,
        subject_zid: str,
        event_id: str,
        kind: str,
    ) -> None:
        uid = hashlib.sha256(
            canonical_json_dumps(
                {
                    "e": event_id,
                    "u": new_id(),
                }
            ).encode("utf-8")
        ).hexdigest()[:32]
        fp = hashlib.sha256(
            canonical_json_dumps(
                {
                    "id": uid,
                    "ty": EVENT_RECORDED,
                }
            ).encode("utf-8")
        ).hexdigest()
        cursor.execute(
            "INSERT INTO events_outbox"
            " (event_id, event_type,"
            " aggregate_id, schema_version,"
            " envelope_version, created_at,"
            " payload, fingerprint,"
            " published_at)"
            " VALUES (?, ?, ?, 1, 1, ?, ?,"
            " ?, NULL)",
            (
                uid,
                EVENT_RECORDED,
                subject_zid,
                self._clock.now(),
                canonical_json_dumps(
                    {
                        "event_id": event_id,
                        "kind": kind,
                    }
                ),
                fp,
            ),
        )

    def record_event(
        self,
        *,
        subject_zid: str,
        actor_zid: str,
        kind: str,
        evidence: bytes,
    ) -> ReputationEvent:
        """One evidence-backed reputation
        event. Refuses self-rating, unknown
        entities, empty evidence and unknown
        kinds."""
        require_non_empty_str(
            subject_zid, "subject_zid"
        )
        require_non_empty_str(
            actor_zid, "actor_zid"
        )
        if kind not in EVENT_KINDS:
            raise ValueError(
                f"unknown kind: {kind}"
            )
        if actor_zid == subject_zid:
            raise SelfReputationError(
                "an entity cannot rate"
                " itself"
            )
        if not evidence:
            raise EmptyEvidenceError(
                "evidence bytes required"
            )
        try:
            self._identity.require_identity(
                subject_zid
            )
        except Exception as exc:
            raise UnknownEntityError(
                "unknown subject:"
                f" {subject_zid}"
            ) from exc
        try:
            self._identity.require_identity(
                actor_zid
            )
        except Exception as exc:
            raise UnknownEntityError(
                "unknown actor:"
                f" {actor_zid}"
            ) from exc
        event_id = f"REP-{new_id()}"
        proof = self._integrity.issue_proof(
            subject=event_id,
            data=evidence,
        )
        evidence_sha = (
            self._integrity.digest_bytes(
                evidence
            )
        )
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            row = cursor.execute(
                "SELECT COALESCE(MAX(seq),"
                " 0) AS last FROM"
                " reputation_events"
                " WHERE subject_zid = ?",
                (subject_zid,),
            ).fetchone()
            seq = (
                int(row["last"]) + 1
                if row is not None
                else 1
            )
            cursor.execute(
                "INSERT INTO"
                " reputation_events"
                " (event_id, seq,"
                "  subject_zid, actor_zid,"
                "  kind, weight,"
                "  evidence_sha, proof_id,"
                "  created_at)"
                " VALUES (?, ?, ?, ?, ?, ?,"
                "  ?, ?, ?)",
                (
                    event_id,
                    seq,
                    subject_zid,
                    actor_zid,
                    kind,
                    self._policy
                    .weight_per_event,
                    evidence_sha,
                    proof.proof_id,
                    now,
                ),
            )
            self._emit(
                cursor,
                subject_zid=subject_zid,
                event_id=event_id,
                kind=kind,
            )
        self._audit.append(
            event_type=EVENT_RECORDED,
            actor=actor_zid,
            subject=subject_zid,
            payload={
                "event_id": event_id,
                "kind": kind,
                "proof_id": (
                    proof.proof_id
                ),
            },
        )
        return ReputationEvent(
            event_id=event_id,
            seq=seq,
            subject_zid=subject_zid,
            actor_zid=actor_zid,
            kind=kind,
            weight=self._policy
            .weight_per_event,
            evidence_sha=evidence_sha,
            proof_id=proof.proof_id,
            created_at=now,
        )

    def _events(
        self, *, subject_zid: str
    ) -> tuple[ReputationEvent, ...]:
        rows = self._db.query_all(
            "SELECT * FROM"
            " reputation_events"
            " WHERE subject_zid = ?"
            " ORDER BY seq",
            (subject_zid,),
        )
        return tuple(
            ReputationEvent(
                event_id=str(
                    r["event_id"]
                ),
                seq=int(r["seq"]),
                subject_zid=str(
                    r["subject_zid"]
                ),
                actor_zid=str(
                    r["actor_zid"]
                ),
                kind=str(r["kind"]),
                weight=float(
                    r["weight"]
                ),
                evidence_sha=str(
                    r["evidence_sha"]
                ),
                proof_id=str(
                    r["proof_id"]
                ),
                created_at=float(
                    r["created_at"]
                ),
            )
            for r in rows
        )

    def score(
        self, *, subject_zid: str
    ) -> int:
        """Deterministic decayed score:
        sum(sign * weight * decay(age)),
        floored at zero."""
        require_non_empty_str(
            subject_zid, "subject_zid"
        )
        now = self._clock.now()
        total = 0.0
        for ev in self._events(
            subject_zid=subject_zid
        ):
            age = max(
                0.0,
                now - ev.created_at,
            )
            factor = (
                self._policy.decay_factor(
                    age_seconds=age
                )
            )
            sign = (
                1.0
                if ev.kind == KIND_POSITIVE
                else -1.0
            )
            total += (
                sign
                * self._policy
                .weight_per_event
                * factor
            )
        return max(
            0, int(round(total))
        )

    def summary(
        self, *, subject_zid: str
    ) -> ReputationSummary:
        events = self._events(
            subject_zid=subject_zid
        )
        positives = sum(
            1
            for e in events
            if e.kind == KIND_POSITIVE
        )
        negatives = sum(
            1
            for e in events
            if e.kind == KIND_NEGATIVE
        )
        last = (
            max(
                e.created_at
                for e in events
            )
            if events
            else None
        )
        return ReputationSummary(
            subject_zid=subject_zid,
            score=self.score(
                subject_zid=subject_zid
            ),
            positive_events=positives,
            negative_events=negatives,
            last_event_at=last,
        )

    def verify_evidence(
        self,
        *,
        event_id: str,
        evidence: bytes,
    ) -> bool:
        """Re-verify historic evidence against
        its stored integrity proof."""
        row = self._db.query_one(
            "SELECT proof_id FROM"
            " reputation_events"
            " WHERE event_id = ?",
            (event_id,),
        )
        if row is None:
            raise NotFoundError(
                "unknown reputation"
                f" event: {event_id}"
            )
        return (
            self._integrity.verify_proof(
                proof_id=str(
                    row["proof_id"]
                ),
                data=evidence,
            )
        )

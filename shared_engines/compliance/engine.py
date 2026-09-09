"""Compliance engine: jurisdiction policies and
audited decisions (multi-jurisdiction by design)."""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass

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
    require_int_range,
    require_non_empty_str,
)
from shared_engines.events.outbox import Outbox
from shared_engines.storage.database import (
    Database,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

EVENT_DECISION = (
    "compliance.decision.recorded"
)

_MIGRATIONS = (
    Migration(
        1,
        "compliance",
        (
            "CREATE TABLE"
            " compliance_policies ("
            " policy_id TEXT PRIMARY KEY,"
            " jurisdiction TEXT NOT NULL,"
            " requirement TEXT NOT NULL,"
            " mandatory INTEGER NOT NULL,"
            " version INTEGER NOT NULL,"
            " active INTEGER NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE INDEX comp_lookup"
            " ON compliance_policies"
            " (jurisdiction,"
            " requirement, active)",
            "CREATE TABLE"
            " compliance_decisions ("
            " decision_id TEXT PRIMARY"
            " KEY,"
            " subject_zid TEXT NOT NULL,"
            " policy_id TEXT NOT NULL,"
            " compliant INTEGER NOT NULL,"
            " reason TEXT NOT NULL,"
            " decided_at REAL NOT NULL)",
        ),
    ),
)


class PolicyNotFoundError(NotFoundError):
    """No active policy for that jurisdiction
    and requirement."""


@dataclass(frozen=True)
class PolicyRecord:
    policy_id: str
    jurisdiction: str
    requirement: str
    mandatory: bool
    version: int
    active: bool


@dataclass(frozen=True)
class ComplianceDecision:
    decision_id: str
    subject_zid: str
    jurisdiction: str
    requirement: str
    compliant: bool
    policy_id: str
    reason: str


class ComplianceEngine:
    """Jurisdiction policies -> audited
    decisions."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        audit: AuditTrail,
        outbox: Outbox,
    ) -> None:
        self._db = db
        self._clock = clock
        self._audit = audit
        self._outbox = outbox
        MigrationRunner(
            db, "compliance", _MIGRATIONS
        ).run(clock)

    def _emit(
        self,
        cursor: sqlite3.Cursor,
        *,
        aggregate: str,
        payload: dict[str, object],
    ) -> None:
        uid = hashlib.sha256(
            canonical_json_dumps(
                {
                    "a": aggregate,
                    "u": new_id(),
                }
            ).encode("utf-8")
        ).hexdigest()[:32]
        fp = hashlib.sha256(
            canonical_json_dumps(
                {
                    "id": uid,
                    "ty": EVENT_DECISION,
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
                EVENT_DECISION,
                aggregate,
                self._clock.now(),
                canonical_json_dumps(
                    payload
                ),
                fp,
            ),
        )

    def register_policy(
        self,
        *,
        jurisdiction: str,
        requirement: str,
        mandatory: bool,
        version: int = 1,
    ) -> PolicyRecord:
        require_non_empty_str(
            jurisdiction, "jurisdiction"
        )
        require_non_empty_str(
            requirement, "requirement"
        )
        require_int_range(
            version, "version", 1, 10**6
        )
        policy_id = (
            f"POL-{new_id()[:12]}"
        )
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO"
                " compliance_policies"
                " (policy_id, jurisdiction,"
                "  requirement, mandatory,"
                "  version, active,"
                "  created_at)"
                " VALUES (?, ?, ?, ?, ?, 1,"
                " ?)",
                (
                    policy_id,
                    jurisdiction,
                    requirement,
                    int(mandatory),
                    version,
                    now,
                ),
            )
        return PolicyRecord(
            policy_id=policy_id,
            jurisdiction=jurisdiction,
            requirement=requirement,
            mandatory=mandatory,
            version=version,
            active=True,
        )

    def _active_policy(
        self,
        jurisdiction: str,
        requirement: str,
    ) -> PolicyRecord:
        row = self._db.query_one(
            "SELECT * FROM"
            " compliance_policies"
            " WHERE jurisdiction = ?"
            " AND requirement = ?"
            " AND active = 1"
            " ORDER BY version DESC"
            " LIMIT 1",
            (jurisdiction, requirement),
        )
        if row is None:
            raise PolicyNotFoundError(
                "no active policy for"
                f" '{jurisdiction}' /"
                f" '{requirement}'"
            )
        return PolicyRecord(
            policy_id=str(
                row["policy_id"]
            ),
            jurisdiction=str(
                row["jurisdiction"]
            ),
            requirement=str(
                row["requirement"]
            ),
            mandatory=bool(
                int(row["mandatory"])
            ),
            version=int(row["version"]),
            active=True,
        )

    def evaluate(
        self,
        *,
        subject_zid: str,
        jurisdiction: str,
        requirement: str,
        satisfied: bool,
    ) -> ComplianceDecision:
        require_non_empty_str(
            subject_zid, "subject_zid"
        )
        policy = self._active_policy(
            jurisdiction, requirement
        )
        compliant = (
            satisfied
            or not policy.mandatory
        )
        if satisfied:
            reason = (
                "requirement satisfied"
            )
        elif compliant:
            reason = (
                "optional requirement"
            )
        else:
            reason = (
                "mandatory"
                " requirement unmet"
            )
        decision_id = (
            f"DEC-{new_id()[:12]}"
        )
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO"
                " compliance_decisions"
                " (decision_id,"
                " subject_zid, policy_id,"
                " compliant, reason,"
                " decided_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    decision_id,
                    subject_zid,
                    policy.policy_id,
                    int(compliant),
                    reason,
                    now,
                ),
            )
            self._emit(
                cursor,
                aggregate=decision_id,
                payload={
                    "jurisdiction": (
                        jurisdiction
                    ),
                    "requirement": (
                        requirement
                    ),
                    "compliant": (
                        compliant
                    ),
                },
            )
        self._audit.append(
            event_type=EVENT_DECISION,
            actor="compliance-engine",
            subject=decision_id,
            payload={
                "compliant": compliant
            },
        )
        return ComplianceDecision(
            decision_id=decision_id,
            subject_zid=subject_zid,
            jurisdiction=jurisdiction,
            requirement=requirement,
            compliant=compliant,
            policy_id=policy.policy_id,
            reason=reason,
        )

    def list_policies(
        self, *, jurisdiction: str
    ) -> tuple[PolicyRecord, ...]:
        rows = self._db.query_all(
            "SELECT * FROM"
            " compliance_policies"
            " WHERE jurisdiction = ?"
            " AND active = 1"
            " ORDER BY requirement,"
            " version DESC",
            (jurisdiction,),
        )
        return tuple(
            PolicyRecord(
                policy_id=str(
                    r["policy_id"]
                ),
                jurisdiction=str(
                    r["jurisdiction"]
                ),
                requirement=str(
                    r["requirement"]
                ),
                mandatory=bool(
                    int(r["mandatory"])
                ),
                version=int(
                    r["version"]
                ),
                active=True,
            )
            for r in rows
        )

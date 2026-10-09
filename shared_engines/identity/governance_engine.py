"""Identity Governance Engine (ID-5). Reglas 63/66/76."""
from __future__ import annotations
import json, uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_gov", (
        "CREATE TABLE IF NOT EXISTS"
        " zid_gov_policies (policy_id TEXT PRIMARY"
        " KEY, name TEXT NOT NULL, rule_json TEXT NOT"
        " NULL, version INTEGER NOT NULL DEFAULT 1,"
        " status TEXT NOT NULL DEFAULT 'activa',"
        " created_by TEXT NOT NULL DEFAULT '',"
        " created_at REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS"
        " zid_gov_decisions (decision_id TEXT PRIMARY"
        " KEY, policy_id TEXT NOT NULL, subject_zid"
        " TEXT NOT NULL, decision TEXT NOT NULL,"
        " reason TEXT NOT NULL DEFAULT '', decided_by"
        " TEXT NOT NULL DEFAULT '', created_at REAL"
        " NOT NULL)",
    )),
)
_ACTIONS = ("register", "verify", "suspend",
            "revoke", "export", "delete")


class GovernanceEngine:
    """Gobierno de identidad (ID-5)."""

    def __init__(self, db: Database, clock: Clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "zid.gov",
                        _MIGRATIONS).run(clock)

    def create_policy(self, *, name, rule,
                      created_by=""):
        if not str(name).strip():
            raise ValueError("name requerido")
        if not isinstance(rule, dict) or not rule:
            raise ValueError(
                "rule debe ser objeto no vacio")
        pid = "ZGP-" + uuid.uuid4().hex[:10]
        self._db.execute(
            "INSERT INTO zid_gov_policies (policy_id,"
            " name, rule_json, version, status,"
            " created_by, created_at)"
            " VALUES (?, ?, ?, 1, 'activa', ?, ?)",
            (pid, str(name),
             json.dumps(rule, sort_keys=True),
             str(created_by), self._clock.now()))
        return {"policy_id": pid, "version": 1}

    def decide(self, *, policy_id, subject_zid,
               action, approve, decided_by="",
               reason=""):
        row = self._db.query_one(
            "SELECT policy_id FROM zid_gov_policies"
            " WHERE policy_id = ?",
            (str(policy_id),))
        if row is None:
            raise KeyError(policy_id)
        if str(action) not in _ACTIONS:
            raise ValueError("action debe ser "
                             + "/".join(_ACTIONS))
        if not str(subject_zid).strip():
            raise ValueError(
                "subject_zid requerido")
        if not str(reason).strip():
            raise ValueError(
                "reason obligatoria (regla 66)")
        did = "ZGD-" + uuid.uuid4().hex[:10]
        dec = "approved" if approve else "rejected"
        self._db.execute(
            "INSERT INTO zid_gov_decisions"
            " (decision_id, policy_id, subject_zid,"
            " decision, reason, decided_by,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?,"
            " ?)",
            (did, str(policy_id),
             str(subject_zid), dec, str(reason),
             str(decided_by), self._clock.now()))
        return {"decision_id": did,
                "decision": dec}

    def decisions_of(self, subject_zid):
        rows = self._db.query_all(
            "SELECT decision_id, policy_id,"
            " decision, reason FROM"
            " zid_gov_decisions WHERE subject_zid ="
            " ? ORDER BY rowid",
            (str(subject_zid),))
        return [{"decision_id": str(
                     r["decision_id"]),
                 "decision": str(r["decision"]),
                 "reason": str(r["reason"])}
                for r in rows]

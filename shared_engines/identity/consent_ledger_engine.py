"""Consent Ledger Engine (ID-3) - registro INMUTABLE
de consentimientos por proposito: append-only con
hash-chain por ZID. Reglas 63/66/76."""
from __future__ import annotations
import hashlib, json, uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_consent_ledger", (
        "CREATE TABLE IF NOT EXISTS"
        " zid_consent_ledger (entry_id TEXT PRIMARY"
        " KEY, zid TEXT NOT NULL, purpose TEXT NOT"
        " NULL, app TEXT NOT NULL DEFAULT '', state"
        " TEXT NOT NULL, scope_json TEXT NOT NULL"
        " DEFAULT '[]', expires_at REAL, prev_hash"
        " TEXT NOT NULL DEFAULT '', entry_hash TEXT"
        " NOT NULL, created_at REAL NOT NULL)",
        "CREATE INDEX ix_cl_zid ON"
        " zid_consent_ledger (zid, purpose)",
    )),
)


def _sha(t):
    return hashlib.sha256(
        t.encode("utf-8")).hexdigest()


class ConsentLedgerEngine:
    """Ledger inmutable de consentimientos (ID-3)."""

    def __init__(self, db: Database, clock: Clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "zid.consentled",
                        _MIGRATIONS).run(clock)

    def _append(self, zid, purpose, app, state,
                scope, expires_at):
        prev = self._db.query_one(
            "SELECT entry_hash FROM"
            " zid_consent_ledger WHERE zid = ?"
            " ORDER BY rowid DESC LIMIT 1",
            (str(zid),))
        ph = (str(prev["entry_hash"])
              if prev else "GENESIS")
        eid = "ZCL-" + uuid.uuid4().hex[:10]
        now = self._clock.now()
        eh = _sha(ph + "|" + eid + "|" + str(zid)
                  + "|" + purpose + "|" + state
                  + "|" + str(expires_at))
        self._db.execute(
            "INSERT INTO zid_consent_ledger"
            " (entry_id, zid, purpose, app, state,"
            " scope_json, expires_at, prev_hash,"
            " entry_hash, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (eid, str(zid), str(purpose), str(app),
             state, json.dumps(list(scope or [])),
             expires_at, ph, eh, now))
        return {"entry_id": eid, "entry_hash": eh}

    def grant(self, *, zid, purpose, app="",
              scope=None, expires_at=None):
        if not str(zid).strip() or \
                not str(purpose).strip():
            raise ValueError(
                "zid y purpose requeridos")
        r = self._append(zid, purpose, str(app),
                         "granted", scope,
                         (float(expires_at)
                          if expires_at is not None
                          else None))
        return {"ok": True,
                "entry_id": r["entry_id"]}

    def revoke(self, *, zid, purpose, app=""):
        st = self.state_of(zid=zid,
                           purpose=purpose,
                           app=app)
        if not st.get("granted"):
            raise ValueError(
                "no hay consentimiento activo")
        r = self._append(zid, purpose, str(app),
                         "revoked", None, None)
        return {"ok": True,
                "entry_id": r["entry_id"]}

    def check(self, *, zid, purpose, app=""):
        now = self._clock.now()
        row = self._db.query_one(
            "SELECT state, expires_at FROM"
            " zid_consent_ledger WHERE zid = ?"
            " AND purpose = ? AND app = ? ORDER"
            " BY rowid DESC LIMIT 1",
            (str(zid), str(purpose), str(app)))
        if row is None:
            return {"granted": False,
                    "reason": "sin registro"}
        if str(row["state"]) != "granted":
            return {"granted": False,
                    "reason": "revocado"}
        if row["expires_at"] is not None and \
                float(row["expires_at"]) <= now:
            return {"granted": False,
                    "reason": "expirado"}
        return {"granted": True}

    def state_of(self, *, zid, purpose, app=""):
        row = self._db.query_one(
            "SELECT state FROM zid_consent_ledger"
            " WHERE zid = ? AND purpose = ? AND"
            " app = ? ORDER BY rowid DESC LIMIT 1",
            (str(zid), str(purpose), str(app)))
        if row is None:
            return {"granted": False}
        return {"granted":
                    str(row["state"])
                    == "granted",
                "state": str(row["state"])}


"""Session & Signature Engine (R-9) - pobla la
carpeta protocol/sessions/signatures/ (la UNICA
vacia de la Red segun la guia): sesiones de ZID con
TTL y FIRMAS de mensajes con sello sha256
verificable. No duplica nada de la auditoria 8c
(no existia sessions en la Red). Patron clase.
Reglas 63/66/68/76."""
from __future__ import annotations
import hashlib
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_sessions", (
        "CREATE TABLE IF NOT EXISTS zid_sessions ("
        " session_id TEXT PRIMARY KEY, zid TEXT NOT"
        " NULL, app TEXT NOT NULL DEFAULT '', status"
        " TEXT NOT NULL DEFAULT 'abierta', opened_at"
        " REAL NOT NULL, expires_at REAL, closed_at"
        " REAL)",
    )),
    Migration(2, "zid_signatures", (
        "CREATE TABLE IF NOT EXISTS zid_signatures ("
        " sig_id TEXT PRIMARY KEY, session_id TEXT"
        " NOT NULL, zid TEXT NOT NULL, message_hash"
        " TEXT NOT NULL, seal TEXT NOT NULL, created"
        "_at REAL NOT NULL)",
    )),
)


def _sha(t):
    return hashlib.sha256(
        t.encode("utf-8")).hexdigest()


class SessionSignatureEngine:
    """Sesiones y firmas de mensajes de la Red."""

    def __init__(self, db: Database, clock: Clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "zid.sess",
                        _MIGRATIONS).run(clock)

    def open_session(self, *, zid, app="",
                     ttl_seconds=None):
        if not str(zid).strip():
            raise ValueError("zid requerido")
        exp = (self._clock.now()
               + float(ttl_seconds)
               if ttl_seconds else None)
        sid = ("ZSES-"
               + uuid.uuid4().hex[:12])
        self._db.execute(
            "INSERT INTO zid_sessions (session_id,"
            " zid, app, status, opened_at,"
            " expires_at, closed_at) VALUES (?, ?,"
            " ?, 'abierta', ?, ?, NULL)",
            (sid, str(zid), str(app),
             self._clock.now(), exp))
        return {"session_id": sid,
                "status": "abierta"}

    def _session(self, session_id):
        row = self._db.query_one(
            "SELECT * FROM zid_sessions WHERE"
            " session_id = ?",
            (str(session_id),))
        if row is None:
            raise LookupError(
                "sesion no encontrada: "
                + str(session_id))
        return row

    def close_session(self, session_id):
        row = self._session(session_id)
        if str(row["status"]) != "abierta":
            raise ValueError("ya cerrada")
        self._db.execute(
            "UPDATE zid_sessions SET status ="
            " 'cerrada', closed_at = ? WHERE"
            " session_id = ?",
            (self._clock.now(),
             str(session_id)))
        return {"session_id": str(session_id)}

    def _live(self, session_id):
        row = self._session(session_id)
        if str(row["status"]) != "abierta":
            raise ValueError("sesion cerrada")
        exp = row["expires_at"]
        if exp is not None and \
                float(exp) <= self._clock.now():
            raise ValueError("sesion expirada")
        return row

    def sign(self, session_id, *, message):
        row = self._live(session_id)
        if not str(message).strip():
            raise ValueError(
                "message requerido")
        mh = _sha(str(message))
        seal = _sha(mh + "|" + str(
            row["session_id"]) + "|"
            + str(row["zid"]))
        sid = ("ZSIG-"
               + uuid.uuid4().hex[:10])
        self._db.execute(
            "INSERT INTO zid_signatures (sig_id,"
            " session_id, zid, message_hash, seal,"
            " created_at) VALUES (?, ?, ?, ?, ?,"
            " ?)",
            (sid, str(row["session_id"]),
             str(row["zid"]), mh, seal,
             self._clock.now()))
        return {"sig_id": sid, "seal": seal}

    def verify(self, sig_id, *, message):
        row = self._db.query_one(
            "SELECT session_id, zid, message_hash,"
            " seal FROM zid_signatures WHERE sig_id"
            " = ?", (str(sig_id),))
        if row is None:
            return {"valid": False,
                    "reason": "no encontrada"}
        mh = _sha(str(message))
        if mh != str(row["message_hash"]):
            return {"valid": False,
                    "reason": "mensaje alterado"}
        seal = _sha(mh + "|" + str(
            row["session_id"]) + "|"
            + str(row["zid"]))
        return {"valid": seal == str(
            row["seal"])}

    def sessions_of(self, zid):
        rows = self._db.query_all(
            "SELECT session_id, app, status FROM"
            " zid_sessions WHERE zid = ? ORDER BY"
            " rowid", (str(zid),))
        return [{"session_id": str(
                     r["session_id"]),
                 "app": str(r["app"]),
                 "status": str(r["status"])}
                for r in rows]


"""Certificate Engine (S-11) - certificados
escolares verificables.

- issue(): emite certificado; si cert_type =
  'GRADO' EXIGE evento PROMOCION real en
  sm_cycle_events (regla 66: no se certifica
  lo que no paso).
- Cadena de hash POR ALUMNO (sha256 sobre el
  entry_hash previo) — mismo patron que
  sm_history del repo.
- verify(code) -> estado + payload.
- revoke(code, reason) -> REVOCADO con motivo.
- verify_chain(student_id) -> True solo si TODA
  la cadena del alumno cuadra (detecta
  alteraciones).

Regla 76: recorrido por rowid (reloj congelado
nunca ordena por timestamp)."""
from __future__ import annotations
import hashlib
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "cert_tables", (
        "CREATE TABLE IF NOT EXISTS"
        " sm_certificates (cert_id TEXT PRIMARY"
        " KEY, cert_code TEXT NOT NULL UNIQUE,"
        " student_id TEXT NOT NULL, cert_type TEXT"
        " NOT NULL, detail TEXT NOT NULL DEFAULT"
        " '', issued_by TEXT NOT NULL DEFAULT '',"
        " status TEXT NOT NULL DEFAULT 'VIGENTE',"
        " revoked_reason TEXT NOT NULL DEFAULT"
        " '', prev_hash TEXT NOT NULL DEFAULT '',"
        " entry_hash TEXT NOT NULL, created_at"
        " REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS"
        " sm_cycle_events (event_id TEXT PRIMARY"
        " KEY, student_id TEXT NOT NULL,"
        " event_type TEXT NOT NULL, school_year"
        " TEXT NOT NULL DEFAULT '', detail TEXT"
        " NOT NULL DEFAULT '', created_at REAL"
        " NOT NULL)",
    )),
)


class CertificateEngine:
    """Certificados verificables (S-11)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.certs",
                        _MIGRATIONS).run(clock)

    def _hash(self, prev, student_id, cert_type,
              detail, ts) -> str:
        base = "|".join([
            str(prev), str(student_id),
            str(cert_type), str(detail),
            str(ts)])
        return hashlib.sha256(
            base.encode("utf-8")).hexdigest()

    def _prev_hash(self, student_id) -> str:
        row = self._db.query_one(
            "SELECT entry_hash FROM"
            " sm_certificates WHERE student_id ="
            " ? ORDER BY rowid DESC LIMIT 1",
            (str(student_id),))
        return (str(row["entry_hash"])
                if row else "")

    def _has_promocion(self, student_id) -> bool:
        row = self._db.query_one(
            "SELECT COUNT(*) AS n FROM"
            " sm_cycle_events WHERE student_id ="
            " ? AND event_type = 'PROMOCION'",
            (str(student_id),))
        return bool(row and int(row["n"]) > 0)

    def issue(self, *, student_id, cert_type,
              detail="", issued_by="") -> dict:
        est = self._db.query_one(
            "SELECT student_id FROM sm_students"
            " WHERE student_id = ?",
            (str(student_id),))
        if est is None:
            raise ValueError(
                "student no existe en el"
                " canonico")
        if str(cert_type) == "GRADO" and \
                not self._has_promocion(
                    student_id):
            raise ValueError(
                "GRADO exige PROMOCION real en"
                " el ciclo (regla 66: nada"
                " falso)")
        prev = self._prev_hash(student_id)
        ts = self._clock.now()
        eh = self._hash(
            prev, student_id, cert_type,
            detail, ts)
        cert_id = ("SMCRT-"
                   + uuid.uuid4().hex[:10])
        code = ("CERT-" + cert_id[5:])
        self._db.execute(
            "INSERT INTO sm_certificates"
            " (cert_id, cert_code, student_id,"
            " cert_type, detail, issued_by,"
            " status, revoked_reason, prev_hash,"
            " entry_hash, created_at) VALUES"
            " (?, ?, ?, ?, ?, ?, 'VIGENTE', '',"
            " ?, ?, ?)",
            (cert_id, code, str(student_id),
             str(cert_type), str(detail),
             str(issued_by), prev, eh, ts))
        return {"cert_id": cert_id,
                "cert_code": code,
                "cert_type": str(cert_type),
                "entry_hash": eh,
                "status": "VIGENTE"}

    def verify(self, cert_code) -> dict:
        row = self._db.query_one(
            "SELECT * FROM sm_certificates WHERE"
            " cert_code = ?",
            (str(cert_code),))
        if not row:
            return {"found": False}
        return {"found": True,
                "cert_code":
                    str(row["cert_code"]),
                "student_id":
                    str(row["student_id"]),
                "cert_type":
                    str(row["cert_type"]),
                "detail": str(row["detail"]),
                "issued_by":
                    str(row["issued_by"]),
                "status": str(row["status"]),
                "revoked_reason":
                    str(row["revoked_reason"]),
                "entry_hash":
                    str(row["entry_hash"])}

    def revoke(self, cert_code, reason) -> dict:
        row = self._db.query_one(
            "SELECT cert_code FROM"
            " sm_certificates WHERE cert_code ="
            " ?", (str(cert_code),))
        if not row:
            raise KeyError(cert_code)
        self._db.execute(
            "UPDATE sm_certificates SET status ="
            " 'REVOCADO', revoked_reason = ?"
            " WHERE cert_code = ?",
            (str(reason), str(cert_code)))
        return {"cert_code": str(cert_code),
                "status": "REVOCADO",
                "reason": str(reason)}

    def verify_chain(self, student_id) -> bool:
        rows = self._db.query_all(
            "SELECT student_id, cert_type,"
            " detail, created_at, prev_hash,"
            " entry_hash FROM sm_certificates"
            " WHERE student_id = ? ORDER BY"
            " rowid", (str(student_id),))
        prev = ""
        for r in rows:
            expect = self._hash(
                prev, r["student_id"],
                r["cert_type"], r["detail"],
                r["created_at"])
            if expect != str(r["entry_hash"]):
                return False
            if prev != str(r["prev_hash"]):
                return False
            prev = str(r["entry_hash"])
        return True

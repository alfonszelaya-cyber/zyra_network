
"""Minor Biometrics Engine (R-4) - la capa de
MENORES de la regla 78 ENCIMA del BiometricsEngine
EXISTENTE (regla 69: ese motor dueno de templates
sellados AES-GCM, 1:N y assurance NO se toca):
- fase PENDING_BIOMETRIC al nacer (regla 78)
- enrolamiento EXIGE tutor activo (GuardianEngine,
  proteccion de menores)
- template JAMAS en claro: hash (regla 63); el
  sellado fuerte vive en BiometricsEngine cuando
  se provee
- actualizacion por crecimiento (reemplazo) y
  revocacion total. Patron _DDL + ensure_db."""
from __future__ import annotations
import hashlib
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_minor_bio", (
        "CREATE TABLE IF NOT EXISTS zid_minor_bio ("
        " bio_id TEXT PRIMARY KEY, zid TEXT NOT"
        " NULL, kind TEXT NOT NULL, template_hash"
        " TEXT NOT NULL, quality INTEGER NOT NULL"
        " DEFAULT 0, status TEXT NOT NULL DEFAULT"
        " 'activa', enrolled_by TEXT NOT NULL"
        " DEFAULT '', created_at REAL NOT NULL)",
    )),
)
_KINDS = ("HUELLA", "ROSTRO", "IRIS")


def _sha(t):
    return hashlib.sha256(
        t.encode("utf-8")).hexdigest()


class MinorBiometricsEngine:
    """Lifecycle biometrico de menores (regla 78)."""

    def __init__(self, db: Database, clock: Clock,
                 guardian_engine=None):
        self._db = db
        self._clock = clock
        self._guardians = guardian_engine
        MigrationRunner(db, "zid.minorbio",
                        _MIGRATIONS).run(clock)

    def phase_of(self, zid):
        rows = self._db.query_all(
            "SELECT bio_id, kind, status, quality"
            " FROM zid_minor_bio WHERE zid = ? ORDER"
            " BY rowid", (str(zid),))
        if not rows:
            return {"zid": str(zid),
                    "phase":
                        "PENDING_BIOMETRIC",
                    "note": "regla 78: nace sin"
                            " biometria",
                    "entries": []}
        active = [r for r in rows
                  if str(r["status"])
                  == "activa"]
        return {"zid": str(zid),
                "phase": ("ENROLADO" if active
                          else "REVOCADO"),
                "entries": [{"bio_id": str(
                    r["bio_id"]),
                    "kind": str(r["kind"]),
                    "status": str(r["status"])}
                    for r in rows]}

    def enroll(self, *, zid, kind, template_b64,
               guardian_zid, quality=0):
        if not str(zid).strip():
            raise ValueError(
                "zid requerido (mismo ZID del"
                " nacimiento, regla 78)")
        k = str(kind).upper()
        if k not in _KINDS:
            raise ValueError("kind debe ser "
                             + "/".join(_KINDS))
        if not str(template_b64).strip():
            raise ValueError(
                "template_b64 requerido")
        if int(quality) < 0 or \
                int(quality) > 100:
            raise ValueError("quality 0..100")
        if self._guardians is None:
            raise ValueError(
                "proteccion de menores: este"
                " engine requiere GuardianEngine")
        g = str(guardian_zid or "").strip()
        if not g:
            raise ValueError(
                "guardian_zid requerido (menor)")
        if not self._guardians.is_guardian(
                g, str(zid)):
            raise ValueError(
                "guardian_zid NO es tutor activo"
                " de este menor (regla 66)")
        th = _sha(str(template_b64))
        dup = self._db.query_one(
            "SELECT bio_id FROM zid_minor_bio WHERE"
            " zid = ? AND kind = ? AND status ="
            " 'activa'", (str(zid), k))
        if dup is not None:
            self._db.execute(
                "UPDATE zid_minor_bio SET status ="
                " 'reemplazada' WHERE bio_id = ?",
                (str(dup["bio_id"]),))
        bid = ("ZMB-"
               + uuid.uuid4().hex[:10])
        self._db.execute(
            "INSERT INTO zid_minor_bio (bio_id,"
            " zid, kind, template_hash, quality,"
            " status, enrolled_by, created_at)"
            " VALUES (?, ?, ?, ?, ?, 'activa', ?,"
            " ?)",
            (bid, str(zid), k, th, int(quality),
             g, self._clock.now()))
        return {"bio_id": bid,
                "template_hash": th}

    def verify(self, *, zid, kind, template_b64):
        k = str(kind).upper()
        th = _sha(str(template_b64))
        row = self._db.query_one(
            "SELECT bio_id, template_hash FROM"
            " zid_minor_bio WHERE zid = ? AND kind"
            " = ? AND status = 'activa'",
            (str(zid), k))
        if row is None:
            return {"matched": False,
                    "reason": "sin plantilla"}
        return {"matched":
                    str(row["template_hash"])
                    == th}

    def revoke_all(self, zid, *, reason):
        if not str(reason).strip():
            raise ValueError(
                "motivo obligatorio")
        n = self._db.query_one(
            "SELECT COUNT(*) AS n FROM zid_minor_bio"
            " WHERE zid = ? AND status = 'activa'",
            (str(zid),))
        self._db.execute(
            "UPDATE zid_minor_bio SET status ="
            " 'revocada' WHERE zid = ? AND status ="
            " 'activa'", (str(zid),))
        return {"zid": str(zid),
                "revoked": int(n["n"])}

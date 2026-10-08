
"""Birth Registry Engine (R-1) - CAPA CIVIL FINA de
nacimiento que COMPONE lo existente de la Red
(regla 69, textual de la guia R-3: "integracion con
Documents/Verification que YA existen - NO motor
nuevo"):
- El ZID del nacido lo emite el IdentityEngine
  EXISTENTE (si se provee; sino queda pendiente)
- El historico vive en LifeHistory EXISTENTE
  (entry_type='birth_registration', su hash-chain
  por ZID - si se provee; fallback: tabla propia
  fina documentada)
- El certificado se sella con DocumentExchange
  EXISTENTE (si se provee; sino guarda hash local)
NO duplica cadenas ni ZIDs. Reglas 63/66/68/76/78."""
from __future__ import annotations
import hashlib
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_births_civil", (
        "CREATE TABLE IF NOT EXISTS zid_births_civil"
        " (birth_id TEXT PRIMARY KEY, child_name"
        " TEXT NOT NULL, birth_date TEXT NOT NULL"
        " DEFAULT '', birth_place TEXT NOT NULL"
        " DEFAULT '', sex TEXT NOT NULL DEFAULT '',"
        " mother_zid TEXT NOT NULL, father_zid TEXT"
        " NOT NULL DEFAULT '', child_zid TEXT NOT"
        " NULL DEFAULT '', cert_code TEXT NOT NULL,"
        " cert_hash TEXT NOT NULL, life_seq INTEGER,"
        " sealed_doc_id TEXT NOT NULL DEFAULT '',"
        " created_at REAL NOT NULL)",
    )),
)
_SEX = ("M", "F", "I")


def _sha(t):
    return hashlib.sha256(
        t.encode("utf-8")).hexdigest()


class BirthRegistryEngine:
    """Capa civil de nacimiento (compone la Red)."""

    def __init__(self, db: Database, clock: Clock,
                 identity_engine=None,
                 life_history=None,
                 document_exchange=None):
        self._db = db
        self._clock = clock
        self._ids = identity_engine
        self._life = life_history
        self._docs = document_exchange
        MigrationRunner(db, "zid.birthcivil",
                        _MIGRATIONS).run(clock)

    def register_birth(self, *, child_name,
                       mother_zid, father_zid="",
                       birth_date="",
                       birth_place="", sex=""):
        if not str(child_name).strip():
            raise ValueError(
                "child_name requerido")
        if not str(mother_zid).strip():
            raise ValueError(
                "mother_zid requerido")
        s = str(sex).upper()
        if s and s not in _SEX:
            raise ValueError("sex debe ser "
                             + "/".join(_SEX))
        child_zid = ""
        if self._ids is not None:
            ident = self._ids.register_identity(
                kind=self._ids_kind(),
                display_name=str(
                    child_name).strip(),
                actor="birth_registry")
            child_zid = str(ident.zid)
        bid = ("ZB-"
               + uuid.uuid4().hex[:10])
        ch = _sha(bid + "|" + str(child_name)
                  + "|" + str(mother_zid) + "|"
                  + str(father_zid) + "|"
                  + str(child_zid))
        cert = ("ZCERT-"
                + uuid.uuid4().hex[:10])
        life_seq = None
        if self._life is not None:
            entry = self._life.append(
                zid=(child_zid or bid),
                entry_type="birth_registration",
                actor_app="axis",
                payload={"birth_id": bid,
                         "child_name": str(
                             child_name).strip(),
                         "mother_zid": str(
                             mother_zid),
                         "father_zid": str(
                             father_zid),
                         "cert_code": cert})
            life_seq = int(entry.entry_seq)
        self._db.execute(
            "INSERT INTO zid_births_civil (birth_id,"
            " child_name, birth_date, birth_place,"
            " sex, mother_zid, father_zid, child_zid,"
            " cert_code, cert_hash, life_seq,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?,"
            " ?, ?, ?, ?, ?, ?)",
            (bid, str(child_name).strip(),
             str(birth_date), str(birth_place), s,
             str(mother_zid), str(father_zid),
             str(child_zid), cert, ch, life_seq,
             self._clock.now()))
        sealed_doc = ""
        if self._docs is not None and child_zid:
            try:
                sealed = self._docs.seal_document(
                    owner_zid=child_zid,
                    title="Acta de nacimiento "
                          + cert,
                    content={"cert_code": cert,
                             "cert_hash": ch,
                             "birth_id": bid},
                    actor_app="axis")
                sealed_doc = str(
                    sealed.get("document_id",
                               ""))
            except Exception:
                sealed_doc = ""
        if sealed_doc:
            self._db.execute(
                "UPDATE zid_births_civil SET"
                " sealed_doc_id = ? WHERE birth_id"
                " = ?", (sealed_doc, bid))
        return {"birth_id": bid,
                "cert_code": cert,
                "cert_hash": ch,
                "child_zid": child_zid,
                "life_seq": life_seq,
                "sealed_doc_id": sealed_doc}

    @staticmethod
    def _ids_kind():
        from shared_engines.identity.contracts import (
            IdentityKind,
        )
        return IdentityKind.PERSON

    def bind_existing_zid(self, birth_id, *, zid):
        row = self._db.query_one(
            "SELECT child_zid FROM zid_births_civil"
            " WHERE birth_id = ?",
            (str(birth_id),))
        if row is None:
            raise KeyError(birth_id)
        if str(row["child_zid"]).strip():
            raise ValueError(
                "ya tiene ZID (regla 78: UNO)")
        if not str(zid).strip():
            raise ValueError("zid requerido")
        self._db.execute(
            "UPDATE zid_births_civil SET child_zid"
            " = ? WHERE birth_id = ?",
            (str(zid), str(birth_id)))
        return {"birth_id": str(birth_id),
                "child_zid": str(zid)}

    def get_birth(self, birth_id):
        row = self._db.query_one(
            "SELECT * FROM zid_births_civil WHERE"
            " birth_id = ?", (str(birth_id),))
        if row is None:
            return {"found": False}
        return {"found": True,
                "child_name": str(
                    row["child_name"]),
                "mother_zid": str(
                    row["mother_zid"]),
                "father_zid": str(
                    row["father_zid"]),
                "child_zid": str(
                    row["child_zid"]),
                "cert_code": str(
                    row["cert_code"]),
                "cert_hash": str(
                    row["cert_hash"]),
                "life_seq": (int(row["life_seq"])
                             if row["life_seq"]
                             is not None
                             else None),
                "sealed_doc_id": str(
                    row["sealed_doc_id"])}

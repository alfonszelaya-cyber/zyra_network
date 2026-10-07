
"""Canonical Bridge (S-1) - puente ADITIVO entre el
registro viejo (SemillaStore / semilla_accounts) y
el canonico (StudentRegistryEngine / sm_students).

REGLA 51 (aditivo): NO cambia el comportamiento
viejo. El server sigue llamando a sus metodos de
siempre; el puente:
1) DUAL-WRITE: tras un alta vieja exitosa, intenta
   registrar al alumno en el canonico (best-effort;
   si los datos no alcanzan el minimo SE-3, queda
   en sm_legacy_pending - NADA falso, regla 66).
2) READ-THROUGH: get_account responde viejo-primero
   (forma compatible garantizada); si el viejo no
   lo tiene, responde el canonico via mapa.
3) JAMAS lanza: cualquier fallo del lado canonico
   degrada a operacion vieja pura.

Tablas: sm_legacy_map (account_id -> student_id)
y sm_legacy_pending (altas que faltan completar
con datos SE-3).

La CONEXION al server vivo (una sola linea:
bridge.wire(store) en el punto de instanciacion)
se hace en RUN 1c con la auditoria LECTURA de
server.py como mapa."""
from __future__ import annotations
import json as _j
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sm_legacy_map", (
        "CREATE TABLE IF NOT EXISTS"
        " sm_legacy_map (account_id TEXT"
        " PRIMARY KEY, student_id TEXT NOT NULL,"
        " created_at REAL NOT NULL)",
    )),
    Migration(2, "sm_legacy_pending", (
        "CREATE TABLE IF NOT EXISTS"
        " sm_legacy_pending (account_id TEXT"
        " PRIMARY KEY, reason TEXT NOT NULL,"
        " payload_json TEXT NOT NULL DEFAULT"
        " '{}', created_at REAL NOT NULL)",
    )),
)

class CanonicalBridge:
    """Puente viejo->canonico (regla 51 aditivo)."""

    def __init__(self, db, clock, registry):
        self._db = db
        self._clock = clock
        self._reg = registry
        MigrationRunner(db, "sm.legacybridge",
                        _MIGRATIONS).run(clock)

    def wire(self, store) -> object:
        """Envuelve los metodos de cuentas que
        existan en el store. Idempotente."""
        for name in ("add_account",
                     "create_account",
                     "register_account"):
            m = getattr(store, name, None)
            if m is not None and not getattr(
                    m, "_zyra_canonical", False):
                setattr(store, name,
                        self._wrap_add(m))
        m = getattr(store, "get_account", None)
        if m is not None and not getattr(
                m, "_zyra_canonical", False):
            setattr(store, "get_account",
                    self._wrap_get(m))
        return store

    # ---------- alta (dual-write) ----------

    def _wrap_add(self, original):
        bridge = self
        def patched(*args, **kwargs):
            res = original(*args, **kwargs)
            try:
                bridge._mirror(args, kwargs, res)
            except Exception:
                pass
            return res
        patched._zyra_canonical = True
        return patched

    def _mirror(self, args, kwargs, res):
        data = dict(kwargs or {})
        if not data and isinstance(res, dict):
            data = dict(res)
        if not data:
            return
        acc = (data.get("account_id")
               or (res or {}).get("account_id")
               or data.get("id") or "")
        name = (data.get("name")
                or data.get("full_name")
                or (res or {}).get("name") or "")
        zid = (data.get("zid")
               or (res or {}).get("zid") or "")
        role = (data.get("role")
                or (res or {}).get("role")
                or "alumno")
        school = (data.get("school")
                  or data.get("institution_id")
                  or "")
        grade = (data.get("grade") or "1")
        if str(role) != "alumno":
            return
        tutores = list(data.get("tutores") or [])
        pick = list(
            data.get("authorized_pickup") or [])
        emg = list(
            data.get("emergency_contacts") or [])
        if (len(tutores) < 1 or len(pick) < 2
                or len(emg) < 1):
            self._pending(
                str(acc), "SE-3 incompleto",
                {"name": str(name),
                 "zid": str(zid)})
            return
        est = self._reg.register(
            full_name=str(name), level="BASICA",
            grade=str(grade),
            institution_id=str(school),
            tutores=tutores,
            authorized_pickup=pick,
            emergency_contacts=emg,
            zid=str(zid),
            zid_status=("PROVISIONAL" if zid
                        else "NONE"))
        if acc:
            self._db.execute(
                "INSERT OR REPLACE INTO"
                " sm_legacy_map (account_id,"
                " student_id, created_at)"
                " VALUES (?, ?, ?)",
                (str(acc),
                 str(est["student_id"]),
                 self._clock.now()))

    def _pending(self, account_id, reason,
                 payload):
        self._db.execute(
            "INSERT OR REPLACE INTO"
            " sm_legacy_pending (account_id,"
            " reason, payload_json, created_at)"
            " VALUES (?, ?, ?, ?)",
            (str(account_id or "SIN_ID"),
             str(reason),
             _j.dumps(payload, default=str),
             self._clock.now()))

    def pending_list(self):
        rows = self._db.query_all(
            "SELECT * FROM sm_legacy_pending"
            " ORDER BY rowid")
        return [dict(r) for r in rows]

    # ---------- lectura ----------

    def _wrap_get(self, original):
        bridge = self
        def patched(*args, **kwargs):
            res = original(*args, **kwargs)
            if res is not None:
                return res
            try:
                acc = None
                if kwargs.get("account_id"):
                    acc = str(
                        kwargs["account_id"])
                elif args:
                    acc = str(args[0])
                if acc:
                    row = self._db.query_one(
                        "SELECT student_id FROM"
                        " sm_legacy_map WHERE"
                        " account_id = ?",
                        (acc,))
                    if row:
                        est = bridge._reg.get(
                            str(row[
                                "student_id"]))
                        if est:
                            return \
                                bridge._canon_shape(
                                    est, acc)
            except Exception:
                pass
            return res
        patched._zyra_canonical = True
        return patched

    def _canon_shape(self, est,
                     account_id) -> dict:
        return {"account_id": str(account_id),
                "student_id":
                    str(est.get("student_id",
                                "")),
                "name":
                    str(est.get("full_name",
                                "")
                        or est.get("name",
                                   "")),
                "zid": str(est.get("zid", "")),
                "role": "alumno",
                "school":
                    str(est.get(
                        "institution_id", "")),
                "grade":
                    str(est.get("grade", "")),
                "canonico": True}

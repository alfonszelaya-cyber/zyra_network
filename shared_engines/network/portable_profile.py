"""Portable identity profile: one registration,
recognized across every authorized app.

Federation layer of the Network:

    App registration (NEXO, Subastas, ...)
          |
          v
    ZID (one identity for the whole Network)
          |
          v
    ProfileRegistry (fields + verification level
                     + source evidence)
          |
          v
    CrossAppAccess (authorized app queries a ZID;
    only permitted fields are returned; every access
    is audited as network.profile.accessed)

Guarantees:

- Profile state lives in its OWN tables (never
  touches identity/ storage).
- Every field carries a verification level:
  SELF_DECLARED or VERIFIED (evidence-backed).
- Apps register with scopes; queries return only
  the intersection of scopes and filled fields.
- Every cross-app access is audited and emits
  network.profile.accessed to the Outbox.
- Transactions never nest: the audit entry is
  written first (own transaction), then the
  outbox event in a separate short transaction.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.serialization import (
    canonical_json_dumps,
)
from shared_engines.common.validation import (
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

EVENT_PROFILE_ACCESSED = (
    "network.profile.accessed"
)
EVENT_PROFILE_UPDATED = (
    "network.profile.updated"
)

LEVEL_SELF = "SELF_DECLARED"
LEVEL_VERIFIED = "VERIFIED"

ALL_FIELDS = (
    "display_name",
    "contact",
    "national_id",
    "id_country",
    "id_type",
    "id_number",
    "nationality",
    "birth_date",
    "address",
)

_MIGRATIONS = (
    Migration(
        1,
        "network_portable_profile",
        (
            "CREATE TABLE app_registry ("
            " app_id TEXT PRIMARY KEY,"
            " display_name TEXT NOT NULL,"
            " scopes TEXT NOT NULL,"
            " registered_at REAL NOT NULL)",
            "CREATE TABLE profile_fields ("
            " zid TEXT NOT NULL,"
            " field TEXT NOT NULL,"
            " value TEXT NOT NULL,"
            " level TEXT NOT NULL,"
            " source_hash TEXT NOT NULL,"
            " updated_at REAL NOT NULL,"
            " PRIMARY KEY (zid, field))",
        ),
    ),
    Migration(
        2,
        "network_profile_consent",
        (
            "CREATE TABLE IF NOT EXISTS profile_consents ("
            " consent_id TEXT PRIMARY KEY, zid TEXT NOT NULL,"
            " app_id TEXT NOT NULL, fields TEXT NOT NULL,"
            " granted_at REAL NOT NULL, expires_at REAL NOT NULL,"
            " face_score REAL, revoked_at REAL)",
        ),
    ),
    Migration(
        3,
        "network_profile_freeze",
        (
            "CREATE TABLE IF NOT EXISTS zid_freezes ("
            " zid TEXT PRIMARY KEY, frozen_at REAL NOT NULL,"
            " reason TEXT, unfreeze_code TEXT)",
        ),
    ),
)


@dataclass(frozen=True)
class AppRegistration:
    app_id: str
    display_name: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class ProfileView:
    """What an app may see for one ZID."""

    zid: str
    fields: dict[str, str]
    levels: dict[str, str]


def _source_hash(
    zid: str, field: str, value: str
) -> str:
    src = canonical_json_dumps(
        {
            "zid": zid,
            "field": field,
            "value": value,
        }
    )
    return hashlib.sha256(
        src.encode("utf-8")
    ).hexdigest()




def age_of(birth_date: str) -> int:
    """AX-ID: edad DERIVADA de
    birth_date (nunca se guarda).
    Formato ISO YYYY-MM-DD."""
    import datetime
    parts = str(birth_date).split("-")
    if len(parts) != 3:
        raise ValueError(
            "birth_date must be"
            " YYYY-MM-DD")
    nac = datetime.date(
        int(parts[0]),
        int(parts[1]),
        int(parts[2]))
    hoy = datetime.date.today()
    edad = hoy.year - nac.year
    if ((hoy.month, hoy.day)
            < (nac.month, nac.day)):
        edad -= 1
    return edad


class ProfileRegistry:
    """Trust profile bound to a Network ZID."""

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
            db,
            "network.portable_profile",
            _MIGRATIONS,
        ).run(clock)

    def register_app(
        self,
        *,
        app_id: str,
        display_name: str,
        scopes: tuple[str, ...],
    ) -> AppRegistration:
        require_non_empty_str(
            app_id, "app_id"
        )
        require_non_empty_str(
            display_name, "display_name"
        )
        clean: list[str] = []
        for scope in scopes:
            require_non_empty_str(
                scope, "scope"
            )
            if scope not in ALL_FIELDS:
                raise ValueError(
                    f"unknown scope:"
                    f" {scope}"
                )
            if scope not in clean:
                clean.append(scope)
        if not clean:
            raise ValueError(
                "at least one scope"
                " required"
            )
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO app_registry"
                " (app_id, display_name,"
                " scopes, registered_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(app_id) DO"
                " UPDATE SET display_name ="
                " excluded.display_name,"
                " scopes = excluded.scopes",
                (
                    app_id,
                    display_name,
                    ",".join(clean),
                    self._clock.now(),
                ),
            )
        return AppRegistration(
            app_id=app_id,
            display_name=display_name,
            scopes=tuple(clean),
        )

    def set_field(
        self,
        *,
        zid: str,
        field: str,
        value: str,
        verified: bool = False,
    ) -> None:
        require_non_empty_str(
            zid, "zid"
        )
        require_non_empty_str(
            field, "field"
        )
        if field not in ALL_FIELDS:
            raise ValueError(
                f"unknown field: {field}"
            )
        require_non_empty_str(
            value, "value"
        )
        level = (
            LEVEL_VERIFIED
            if verified
            else LEVEL_SELF
        )
        src = _source_hash(
            zid, field, value
        )
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO profile_fields"
                " (zid, field, value, level,"
                "  source_hash, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(zid, field)"
                " DO UPDATE SET value ="
                " excluded.value, level ="
                " excluded.level,"
                " source_hash ="
                " excluded.source_hash,"
                " updated_at ="
                " excluded.updated_at",
                (
                    zid,
                    field,
                    value,
                    level,
                    src,
                    self._clock.now(),
                ),
            )
            self._emit(
                cursor,
                event_type=(
                    EVENT_PROFILE_UPDATED
                ),
                aggregate=zid,
                payload={
                    "field": field,
                    "level": level,
                },
            )

    def _emit(
        self,
        cursor: sqlite3.Cursor,
        *,
        event_type: str,
        aggregate: str,
        payload: dict[str, object],
    ) -> None:
        """Durably enqueue an outbox event
        inside the caller's transaction."""
        event_id_src = canonical_json_dumps(
            {
                "t": event_type,
                "a": aggregate,
                "p": payload,
                "ts": self._clock.now(),
            }
        )
        event_id = hashlib.sha256(
            event_id_src.encode("utf-8")
        ).hexdigest()[:32]
        fp = hashlib.sha256(
            canonical_json_dumps(
                {
                    "id": event_id,
                    "ty": event_type,
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
                event_id,
                event_type,
                aggregate,
                self._clock.now(),
                canonical_json_dumps(
                    payload
                ),
                fp,
            ),
        )

    def app_scopes(
        self, app_id: str
    ) -> tuple[str, ...] | None:
        row = self._db.query_one(
            "SELECT scopes FROM"
            " app_registry"
            " WHERE app_id = ?",
            (app_id,),
        )
        if row is None:
            return None
        return tuple(
            s
            for s in str(
                row["scopes"]
            ).split(",")
            if s
        )

    def view_for_app(
        self,
        *,
        app_id: str,
        zid: str,
    ) -> ProfileView:
        """Authorized cross-app read.

        Only fields in the app's scopes AND
        present in the profile are returned.
        Every call is audited and emits
        network.profile.accessed.

        Transaction discipline: the audit
        append owns its transaction, so it runs
        BEFORE the short outbox transaction
        (no nesting).
        """
        require_non_empty_str(
            app_id, "app_id"
        )
        require_non_empty_str(
            zid, "zid"
        )
        scopes = self.app_scopes(app_id)
        if scopes is None:
            raise PermissionError(
                "app not registered:"
                f" {app_id}"
            )
        fields: dict[str, str] = {}
        levels: dict[str, str] = {}
        rows = self._db.query_all(
            "SELECT field, value, level"
            " FROM profile_fields"
            " WHERE zid = ?",
            (zid,),
        )
        for row in rows:
            field = str(row["field"])
            if field not in scopes:
                continue
            fields[field] = str(
                row["value"]
            )
            levels[field] = str(
                row["level"]
            )
        accessed_fields = sorted(
            fields.keys()
        )
        self._audit.append(
            event_type=(
                EVENT_PROFILE_ACCESSED
            ),
            actor=app_id,
            subject=zid,
            payload={
                "fields": accessed_fields,
            },
        )
        with self._db.transaction() as cursor:
            self._emit(
                cursor,
                event_type=(
                    EVENT_PROFILE_ACCESSED
                ),
                aggregate=zid,
                payload={
                    "app": app_id,
                    "fields": (
                        accessed_fields
                    ),
                },
            )
        return ProfileView(
            zid=zid,
            fields=fields,
            levels=levels,
        )

    def universal_view(
        self,
        *,
        app_id: str,
        zid: str,
    ) -> dict[str, object]:
        """AX-ID: EL paquete del
        verificador (banco, consulado,
        empleador). Campos universales
        con nivel + edad DERIVADA +
        auditoria del acceso."""
        require_non_empty_str(
            app_id, "app_id")
        require_non_empty_str(
            zid, "zid")
        if self.is_frozen(zid=zid):
            raise FrozenIdentityError(
                "ZID congelado por su dueno (AX-FREEZE)")
        scopes = self.app_scopes(
            app_id)
        if scopes is None:
            raise PermissionError(
                "app not registered:"
                " " + app_id)
        vista = self.view_for_app(
            app_id=app_id, zid=zid)
        campos: dict[str, str] = {}
        niveles: dict[str, str] = {}
        for f in (
            "display_name",
            "national_id",
            "id_country",
            "id_type",
            "id_number",
            "nationality",
            "birth_date",
            "address",
        ):
            if f in vista.fields:
                campos[f] = (
                    vista.fields[f])
                niveles[f] = (
                    vista.levels[f])
        edad = None
        if "birth_date" in campos:
            edad = age_of(
                campos["birth_date"])
        self._audit.append(
            event_type=(
                "network.profile"
                ".universal_access"),
            actor=app_id,
            subject=zid,
            payload={
                "fields": sorted(
                    campos.keys()),
            },
        )
        return {
            "zid": zid,
            "fields": campos,
            "levels": niveles,
            "age": edad,
        }

    def verification_verdict(
        self,
        *,
        app_id: str,
        zid: str,
        face_verdict: dict[str, object],
        signer,
        clock: Clock,
    ) -> dict[str, object]:
        """AX-VERIF: EL veredicto de verificacion para bancos/consulados/empleadores. Une biometria 1:1 + universal_view + FIRMA de la Red (prueba verificable offline). Scope gobierna; acceso auditado."""
        from shared_engines.common.serialization import canonical_json_dumps
        import time as _time
        require_non_empty_str(app_id, "app_id")
        require_non_empty_str(zid, "zid")
        if self.is_frozen(zid=zid):
            raise FrozenIdentityError(
                "ZID congelado por su dueno (AX-FREEZE)")
        base = self.universal_view(app_id=app_id, zid=zid)
        match = bool(face_verdict.get("match"))
        score = float(face_verdict.get("score", 0.0))
        verdict = {
            "zid": zid,
            "verified_person": match,
            "face_score": score,
            "fields": base["fields"],
            "levels": base["levels"],
            "age": base["age"],
            "verified_at": _time.time(),
            "issuer": "zyra-network",
        }
        payload = canonical_json_dumps(verdict).encode("utf-8")
        firma = signer.sign(payload)
        verd = dict(verdict)
        verd["signature"] = firma.hex()
        self._audit.append(
            event_type="network.verification.verdict",
            actor=app_id,
            subject=zid,
            payload={"match": match, "score": score},
        )
        return verd

    def grant_consent(self, *, zid: str, app_id: str, fields: tuple[str, ...], face_score: float, ttl_hours: float = 24.0) -> dict[str, object]:
        """AX-CONSENT: el dueno autoriza a una app ver campos especificos por tiempo limitado. Evidencia: puntaje biometrico."""
        import secrets
        require_non_empty_str(zid, "zid")
        require_non_empty_str(app_id, "app_id")
        if not fields:
            raise ValueError("fields required")
        if not (0.0 <= face_score <= 1.0):
            raise ValueError("face_score invalid")
        now = self._clock.now()
        consent_id = "CON-" + secrets.token_hex(6)
        expires = now + ttl_hours * 3600.0
        with self._db.transaction() as cursor:
            cursor.execute("INSERT INTO profile_consents (consent_id, zid, app_id, fields, granted_at, expires_at, face_score) VALUES (?, ?, ?, ?, ?, ?, ?)", (consent_id, zid, app_id, ",".join(fields), now, expires, face_score))
        self._audit.append(event_type="network.consent.granted", actor=zid, subject=consent_id, payload={"app": app_id, "fields": list(fields)})
        return {"consent_id": consent_id, "expires_at": expires, "fields": list(fields)}

    def check_consent(self, *, zid: str, app_id: str):
        """Campos autorizados vigentes; None si no hay o expiro."""
        now = self._clock.now()
        rows = self._db.query_all("SELECT fields FROM profile_consents WHERE zid = ? AND app_id = ? AND expires_at > ? AND revoked_at IS NULL", (zid, app_id, now))
        if not rows:
            return None
        campos = set()
        for r in rows:
            campos.update(str(r["fields"]).split(","))
        return tuple(sorted(campos))

    def revoke_consent(self, *, zid: str, consent_id: str) -> None:
        require_non_empty_str(consent_id, "consent_id")
        with self._db.transaction() as cursor:
            cursor.execute("UPDATE profile_consents SET revoked_at = ? WHERE consent_id = ? AND zid = ?", (self._clock.now(), consent_id, zid))
        self._audit.append(event_type="network.consent.revoked", actor=zid, subject=consent_id, payload={})

    def consents_of(self, *, zid: str) -> tuple[dict[str, object], ...]:
        """El dueno ve sus permisos: quien, que campos, hasta cuando."""
        rows = self._db.query_all("SELECT * FROM profile_consents WHERE zid = ? ORDER BY granted_at DESC", (zid,))
        return tuple({"consent_id": str(r["consent_id"]), "app_id": str(r["app_id"]), "fields": str(r["fields"]).split(","), "expires_at": float(r["expires_at"]), "revoked": r["revoked_at"] is not None} for r in rows)

    def freeze_zid(self, *, zid: str, reason: str = "") -> dict[str, str]:
        """AX-FREEZE: boton de panico. Congela el ZID: NINGUNA verificacion pasa. Devuelve el codigo de desbloqueo de un solo uso."""
        import secrets
        require_non_empty_str(zid, "zid")
        code = secrets.token_hex(4)
        with self._db.transaction() as cursor:
            cursor.execute("INSERT INTO zid_freezes (zid, frozen_at, reason, unfreeze_code) VALUES (?, ?, ?, ?) ON CONFLICT(zid) DO UPDATE SET frozen_at = excluded.frozen_at, reason = excluded.reason, unfreeze_code = excluded.unfreeze_code", (zid, self._clock.now(), reason, code))
        self._audit.append(event_type="network.identity.frozen", actor=zid, subject=zid, payload={"reason": reason})
        return {"zid": zid, "unfreeze_code": code}

    def is_frozen(self, *, zid: str) -> bool:
        row = self._db.query_one("SELECT 1 FROM zid_freezes WHERE zid = ?", (zid,))
        return row is not None

    def unfreeze_zid(self, *, zid: str, code: str) -> bool:
        """Descongela SOLO con el codigo entregado al congelar."""
        require_non_empty_str(code, "code")
        row = self._db.query_one("SELECT unfreeze_code FROM zid_freezes WHERE zid = ?", (zid,))
        if row is None:
            return False
        if str(row["unfreeze_code"]) != code:
            return False
        with self._db.transaction() as cursor:
            cursor.execute("DELETE FROM zid_freezes WHERE zid = ?", (zid,))
        self._audit.append(event_type="network.identity.unfrozen", actor=zid, subject=zid, payload={})
        return True

class FrozenIdentityError(PermissionError):
    """AX-FREEZE: el ZID esta congelado por su dueno."""

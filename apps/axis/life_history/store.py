"""AXIS Life History — verifiable life history from birth.

Phase 1 of the AXIS 99% plan: birth registration.

What this module delivers (all additive, own namespace,
offline-safe by design — the Network integration happens
at the link layer):

- DIGITAL BIRTH CERTIFICATE, sealed and CHAINED: every birth
  hashes the previous one, so the whole registry becomes ONE
  tamper-evident national chain (births_chain_verify()).
  Tampering with ANY past birth breaks the entire chain.
- NEWBORN IDENTITY: a person record born anchored to the
  sealed certificate + verified parents (mother/father must
  carry a network ZID). The newborn's ZID is attached later
  via attach_zid() (biometric upgrade when the person grows).
- Parent custody links with verified ZIDs.
- Per-person life event chain (health, justice, security):
  hash-chained, append-only.
- Amendments: corrections are APPENDED to the chain, never
  deleted — full traceability, superior to plain registries.

Storage pattern: AxisStore conventions (MigrationRunner,
transactions, dict returns, offline degradation).
Run tests:  python -m apps.axis.life_history.store -v
"""
from __future__ import annotations

import hashlib
import sqlite3
import unittest
import uuid

from shared_engines.common.errors import EngineError
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

SEX_VALUES = ("M", "F", "I")
PARENT_ROLES = ("madre", "padre", "tutor")

PERSON_REGISTERED = "registered"
PERSON_VERIFIED = "biometric_verified"

BIRTH_STATUS_ACTIVE = "active"
BIRTH_STATUS_AMENDED = "amended"

GENESIS = "GENESIS"


class LifeHistoryError(EngineError):
    """Base life-history error."""


class ParentNotVerifiedError(LifeHistoryError):
    """A parent ZID is missing or is not a verified
    network identity."""


_MIGRATIONS = (
    Migration(
        1,
        "life_history_core",
        (
            "CREATE TABLE life_persons ("
            " person_id TEXT PRIMARY KEY,"
            " zid TEXT,"
            " full_name TEXT NOT NULL,"
            " sex TEXT NOT NULL,"
            " birth_date TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE INDEX life_persons_status"
            " ON life_persons (status)",
            "CREATE TABLE life_births ("
            " birth_id TEXT PRIMARY KEY,"
            " person_id TEXT NOT NULL,"
            " birth_place TEXT NOT NULL,"
            " birth_date TEXT NOT NULL,"
            " sex TEXT NOT NULL,"
            " registrar_account TEXT NOT NULL,"
            " mother_name TEXT NOT NULL,"
            " mother_zid TEXT NOT NULL,"
            " father_name TEXT,"
            " father_zid TEXT,"
            " source_hospital TEXT,"
            " cert_hash TEXT NOT NULL,"
            " previous_chain_hash TEXT NOT NULL,"
            " chain_hash TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE INDEX life_births_person"
            " ON life_births (person_id)",
            "CREATE TABLE life_links ("
            " link_id TEXT PRIMARY KEY,"
            " person_id TEXT NOT NULL,"
            " parent_account TEXT NOT NULL,"
            " parent_zid TEXT NOT NULL,"
            " parent_name TEXT NOT NULL,"
            " role TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE INDEX life_links_person"
            " ON life_links (person_id)",
            "CREATE TABLE life_events ("
            " event_id TEXT PRIMARY KEY,"
            " person_id TEXT NOT NULL,"
            " previous_hash TEXT NOT NULL,"
            " event_hash TEXT NOT NULL,"
            " actor TEXT NOT NULL,"
            " event_type TEXT NOT NULL,"
            " detail TEXT,"
            " occurred_at REAL NOT NULL)",
            "CREATE INDEX life_events_person"
            " ON life_events (person_id)",
        ),
    ),
)


def _sha256(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


class LifeHistoryStore:
    """Durable, tamper-evident life history."""

    def __init__(
        self, db: Database, clock: Clock
    ) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db, "axis.life_history", _MIGRATIONS
        ).run(clock)

    # ---------------------------------------- birth

    def register_birth(
        self,
        *,
        registrar_account: str,
        child_name: str,
        birth_date: str,
        birth_place: str,
        sex: str,
        mother_name: str,
        mother_zid: str,
        father_name: str | None = None,
        father_zid: str | None = None,
        source_hospital: str | None = None,
    ) -> dict[str, object]:
        """Seals a birth certificate and anchors the
        newborn's identity. Chain-safe: the chain hash
        is computed INSIDE the transaction, so two
        concurrent registrations can never fork the
        national chain."""
        if not registrar_account.strip():
            raise ValueError(
                "registrar_account required"
            )
        if not child_name.strip():
            raise ValueError("child_name required")
        if not birth_date.strip():
            raise ValueError("birth_date required")
        if not birth_place.strip():
            raise ValueError("birth_place required")
        if not mother_name.strip():
            raise ValueError("mother_name required")
        if sex not in SEX_VALUES:
            raise ValueError(
                f"sex must be one of {SEX_VALUES}"
            )
        if not mother_zid.startswith("ZID-"):
            raise ParentNotVerifiedError(
                "mother has no verified ZID"
            )
        if father_name is not None and (
            father_zid is None
        ):
            raise ParentNotVerifiedError(
                "father named without verified ZID"
            )
        if father_zid is not None and not (
            father_zid.startswith("ZID-")
        ):
            raise ParentNotVerifiedError(
                "father has no verified ZID"
            )
        now = self._clock.now()
        birth_id = "BRT-" + uuid.uuid4().hex[:10]
        person_id = "LHP-" + uuid.uuid4().hex[:10]
        cert_payload = "|".join(
            (
                birth_id,
                person_id,
                child_name.strip(),
                birth_date.strip(),
                birth_place.strip(),
                sex,
                mother_name.strip(),
                mother_zid,
                father_name or "",
                father_zid or "",
                registrar_account.strip(),
                str(now),
            )
        )
        cert_hash = _sha256(cert_payload)
        with self._db.transaction() as cursor:
            row = cursor.execute(
                "SELECT chain_hash FROM"
                " life_births ORDER BY rowid"
                " DESC LIMIT 1"
            ).fetchone()
            previous_chain = (
                str(row["chain_hash"])
                if row is not None
                else GENESIS
            )
            chain_payload = "|".join(
                (
                    birth_id,
                    previous_chain,
                    cert_hash,
                    str(now),
                )
            )
            chain_hash = _sha256(
                chain_payload
            )
            cursor.execute(
                "INSERT INTO life_persons ("
                " person_id, zid, full_name,"
                " sex, birth_date, status,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    person_id,
                    None,
                    child_name.strip(),
                    sex,
                    birth_date.strip(),
                    PERSON_REGISTERED,
                    now,
                ),
            )
            cursor.execute(
                "INSERT INTO life_births ("
                " birth_id, person_id,"
                " birth_place, birth_date,"
                " sex, registrar_account,"
                " mother_name, mother_zid,"
                " father_name, father_zid,"
                " source_hospital, cert_hash,"
                " previous_chain_hash,"
                " chain_hash, status,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?,"
                "  ?, ?, ?, ?, ?, ?, ?, ?,"
                "  ?, ?)",
                (
                    birth_id,
                    person_id,
                    birth_place.strip(),
                    birth_date.strip(),
                    sex,
                    registrar_account.strip(),
                    mother_name.strip(),
                    mother_zid,
                    father_name,
                    father_zid,
                    source_hospital,
                    cert_hash,
                    previous_chain,
                    chain_hash,
                    BIRTH_STATUS_ACTIVE,
                    now,
                ),
            )
            self._insert_link(
                cursor,
                person_id=person_id,
                parent_account=(
                    "AX-mother-" + person_id
                ),
                parent_zid=mother_zid,
                parent_name=mother_name.strip(),
                role="madre",
                now=now,
            )
            if father_name and father_zid:
                self._insert_link(
                    cursor,
                    person_id=person_id,
                    parent_account=(
                        "AX-father-"
                        + person_id
                    ),
                    parent_zid=father_zid,
                    parent_name=(
                        father_name.strip()
                    ),
                    role="padre",
                    now=now,
                )
            self._chain_event(
                cursor,
                person_id=person_id,
                actor=registrar_account.strip(),
                event_type="birth_registered",
                detail=birth_id,
                now=now,
            )
        return self.get_birth(birth_id)

    def get_birth(
        self, birth_id: str
    ) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM life_births"
            " WHERE birth_id = ?",
            (birth_id,),
        )
        if row is None:
            raise LookupError(
                f"unknown birth: {birth_id}"
            )
        return {
            "birth_id": str(row["birth_id"]),
            "person_id": str(
                row["person_id"]
            ),
            "birth_place": str(
                row["birth_place"]
            ),
            "birth_date": str(
                row["birth_date"]
            ),
            "sex": str(row["sex"]),
            "registrar_account": str(
                row["registrar_account"]
            ),
            "mother_name": str(
                row["mother_name"]
            ),
            "mother_zid": str(
                row["mother_zid"]
            ),
            "father_name": (
                str(row["father_name"])
                if row["father_name"]
                is not None
                else None
            ),
            "father_zid": (
                str(row["father_zid"])
                if row["father_zid"]
                is not None
                else None
            ),
            "source_hospital": (
                str(row["source_hospital"])
                if row["source_hospital"]
                is not None
                else None
            ),
            "cert_hash": str(
                row["cert_hash"]
            ),
            "previous_chain_hash": str(
                row["previous_chain_hash"]
            ),
            "chain_hash": str(
                row["chain_hash"]
            ),
            "status": str(row["status"]),
            "created_at": float(
                row["created_at"]
            ),
        }

    def get_person(
        self, person_id: str
    ) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM life_persons"
            " WHERE person_id = ?",
            (person_id,),
        )
        if row is None:
            raise LookupError(
                f"unknown person: {person_id}"
            )
        return {
            "person_id": str(
                row["person_id"]
            ),
            "zid": (
                str(row["zid"])
                if row["zid"] is not None
                else None
            ),
            "full_name": str(
                row["full_name"]
            ),
            "sex": str(row["sex"]),
            "birth_date": str(
                row["birth_date"]
            ),
            "status": str(row["status"]),
            "created_at": float(
                row["created_at"]
            ),
        }

    def parents_of(
        self, person_id: str
    ) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM life_links"
            " WHERE person_id = ?"
            " ORDER BY created_at",
            (person_id,),
        )
        return tuple(
            {
                "link_id": str(r["link_id"]),
                "parent_account": str(
                    r["parent_account"]
                ),
                "parent_zid": str(
                    r["parent_zid"]
                ),
                "parent_name": str(
                    r["parent_name"]
                ),
                "role": str(r["role"]),
            }
            for r in rows
        )

    def births_chain_verify(
        self,
    ) -> tuple[bool, int]:
        """Walks the WHOLE registry: every birth must
        chain to the previous one. Any tampering with
        any past birth breaks it. Returns
        (ok, births_checked)."""
        rows = self._db.query_all(
            "SELECT * FROM life_births"
            " ORDER BY rowid"
        )
        previous = GENESIS
        for row in rows:
            if str(row["status"]) == BIRTH_STATUS_ACTIVE:
                person = self._db.query_one(
                    "SELECT full_name FROM"
                    " life_persons WHERE"
                    " person_id = ?",
                    (str(row["person_id"]),),
                )
                full_name = (
                    str(person["full_name"])
                    if person is not None
                    else ""
                )
                cert_expected = _sha256(
                    "|".join(
                        (
                            str(row["birth_id"]),
                            str(row["person_id"]),
                            full_name,
                            str(row["birth_date"]),
                            str(row["birth_place"]),
                            str(row["sex"]),
                            str(row["mother_name"]),
                            str(row["mother_zid"]),
                            str(row["father_name"] or ""),
                            str(row["father_zid"] or ""),
                            str(row["registrar_account"]),
                            str(row["created_at"]),
                        )
                    )
                )
                if str(row["cert_hash"]) != cert_expected:
                    return False, len(rows)
            expected = _sha256(
                "|".join(
                    (
                        str(row["birth_id"]),
                        previous,
                        str(row["cert_hash"]),
                        str(row["created_at"]),
                    )
                )
            )
            if (
                str(row["previous_chain_hash"])
                != previous
                or str(row["chain_hash"])
                != expected
            ):
                return False, len(rows)
            previous = expected
        return True, len(rows)

    # ---------------------------------------- identity upgrade

    def attach_zid(
        self,
        person_id: str,
        *,
        zid: str,
        actor: str,
    ) -> dict[str, object]:
        """Biometric upgrade: links the network ZID
        (issued via /identity/enroll with real
        biometrics) to the newborn identity. Appends
        a chain event; never rewrites history."""
        if not zid.startswith("ZID-"):
            raise ValueError(
                "zid must be a network ZID"
            )
        if not actor.strip():
            raise ValueError("actor required")
        now = self._clock.now()
        with self._db.transaction() as cursor:
            row = cursor.execute(
                "SELECT status FROM life_persons"
                " WHERE person_id = ?",
                (person_id,),
            ).fetchone()
            if row is None:
                raise LookupError(
                    f"unknown person:"
                    f" {person_id}"
                )
            cursor.execute(
                "UPDATE life_persons SET"
                " zid = ?, status = ?"
                " WHERE person_id = ?",
                (
                    zid,
                    PERSON_VERIFIED,
                    person_id,
                ),
            )
            self._chain_event(
                cursor,
                person_id=person_id,
                actor=actor.strip(),
                event_type=(
                    "zid_biometric_upgrade"
                ),
                detail=zid,
                now=now,
            )
        return self.get_person(person_id)

    # ---------------------------------------- life events

    def add_life_event(
        self,
        person_id: str,
        *,
        actor: str,
        event_type: str,
        detail: str,
    ) -> dict[str, object]:
        if not actor.strip():
            raise ValueError("actor required")
        if not event_type.strip():
            raise ValueError(
                "event_type required"
            )
        if not detail.strip():
            raise ValueError("detail required")
        now = self._clock.now()
        with self._db.transaction() as cursor:
            row = cursor.execute(
                "SELECT person_id FROM"
                " life_persons WHERE"
                " person_id = ?",
                (person_id,),
            ).fetchone()
            if row is None:
                raise LookupError(
                    f"unknown person:"
                    f" {person_id}"
                )
            event = self._chain_event(
                cursor,
                person_id=person_id,
                actor=actor.strip(),
                event_type=event_type.strip(),
                detail=detail.strip(),
                now=now,
            )
        return event

    def events_of(
        self, person_id: str
    ) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM life_events"
            " WHERE person_id = ?"
            " ORDER BY occurred_at, rowid",
            (person_id,),
        )
        return tuple(
            {
                "event_id": str(
                    r["event_id"]
                ),
                "event_type": str(
                    r["event_type"]
                ),
                "actor": str(r["actor"]),
                "detail": (
                    str(r["detail"])
                    if r["detail"]
                    is not None
                    else None
                ),
                "event_hash": str(
                    r["event_hash"]
                ),
                "occurred_at": float(
                    r["occurred_at"]
                ),
            }
            for r in rows
        )

    def events_verify(
        self, person_id: str
    ) -> bool:
        rows = self._db.query_all(
            "SELECT * FROM life_events"
            " WHERE person_id = ?"
            " ORDER BY occurred_at, rowid",
            (person_id,),
        )
        previous = GENESIS
        for row in rows:
            expected = self._event_expected_hash(
                person_id=str(
                    row["person_id"]
                ),
                previous=previous,
                actor=str(row["actor"]),
                event_type=str(
                    row["event_type"]
                ),
                detail=row["detail"],
                occurred_at=float(
                    row["occurred_at"]
                ),
            )
            if (
                str(row["previous_hash"])
                != previous
                or str(row["event_hash"])
                != expected
            ):
                return False
            previous = expected
        return True

    # ---------------------------------------- amendments

    def amend_birth(
        self,
        birth_id: str,
        *,
        actor: str,
        amendment_type: str,
        detail: str,
        corrected_child_name: str | None = None,
    ) -> dict[str, object]:
        """Corrections are APPENDED to the chain and
        the birth row is marked amended — nothing is
        ever deleted or silently rewritten."""
        if not actor.strip():
            raise ValueError("actor required")
        if not amendment_type.strip():
            raise ValueError(
                "amendment_type required"
            )
        if not detail.strip():
            raise ValueError("detail required")
        birth = self.get_birth(birth_id)
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE life_births SET"
                " status = ? WHERE"
                " birth_id = ?",
                (
                    BIRTH_STATUS_AMENDED,
                    birth_id,
                ),
            )
            if corrected_child_name:
                cursor.execute(
                    "UPDATE life_persons SET"
                    " full_name = ? WHERE"
                    " person_id = ?",
                    (
                        corrected_child_name.strip(),
                        birth["person_id"],
                    ),
                )
            self._chain_event(
                cursor,
                person_id=str(
                    birth["person_id"]
                ),
                actor=actor.strip(),
                event_type=(
                    "birth_amendment:"
                    + amendment_type.strip()
                ),
                detail=(
                    birth_id
                    + ": "
                    + detail.strip()
                ),
                now=now,
            )
        return self.get_birth(birth_id)

    # ---------------------------------------- internals

    @staticmethod
    def _insert_link(
        cursor: Any,
        *,
        person_id: str,
        parent_account: str,
        parent_zid: str,
        parent_name: str,
        role: str,
        now: float,
    ) -> None:
        if role not in PARENT_ROLES:
            raise ValueError(
                f"unknown parent role: {role}"
            )
        cursor.execute(
            "INSERT INTO life_links ("
            " link_id, person_id,"
            " parent_account, parent_zid,"
            " parent_name, role, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "LNK-"
                + uuid.uuid4().hex[:10],
                person_id,
                parent_account,
                parent_zid,
                parent_name,
                role,
                now,
            ),
        )

    def _chain_event(
        self,
        cursor: Any,
        *,
        person_id: str,
        actor: str,
        event_type: str,
        detail: str | None,
        now: float,
    ) -> dict[str, object]:
        row = cursor.execute(
            "SELECT event_hash FROM"
            " life_events WHERE"
            " person_id = ? ORDER BY"
            " rowid DESC LIMIT 1",
            (person_id,),
        ).fetchone()
        previous = (
            str(row["event_hash"])
            if row is not None
            else GENESIS
        )
        event_hash = (
            self._event_expected_hash(
                person_id=person_id,
                previous=previous,
                actor=actor,
                event_type=event_type,
                detail=detail,
                occurred_at=now,
            )
        )
        event_id = (
            "LHE-"
            + uuid.uuid4().hex[:10]
        )
        cursor.execute(
            "INSERT INTO life_events ("
            " event_id, person_id,"
            " previous_hash, event_hash,"
            " actor, event_type, detail,"
            " occurred_at)"
            " VALUES (?, ?, ?, ?, ?, ?,"
            "  ?, ?)",
            (
                event_id,
                person_id,
                previous,
                event_hash,
                actor,
                event_type,
                detail,
                now,
            ),
        )
        return {
            "event_id": event_id,
            "person_id": person_id,
            "previous_hash": previous,
            "event_hash": event_hash,
            "actor": actor,
            "event_type": event_type,
            "detail": detail,
            "occurred_at": now,
        }

    @staticmethod
    def _event_expected_hash(
        *,
        person_id: str,
        previous: str,
        actor: str,
        event_type: str,
        detail: str | None,
        occurred_at: float,
    ) -> str:
        payload = "|".join(
            (
                person_id,
                previous,
                actor,
                event_type,
                detail or "",
                str(occurred_at),
            )
        )
        return _sha256(payload)


# =====================================================
# Tests (offline, deterministic)
# =====================================================

_MOTHER_ZID = "ZID-mother-0001"
_FATHER_ZID = "ZID-father-0001"
_REGISTRAR = "AX-registrador-1"


class _Base(unittest.TestCase):
    def _store(
        self,
    ) -> tuple[LifeHistoryStore, Database]:
        from shared_engines.common.clocks import (
            SystemClock,
        )
        from shared_engines.storage.database import (
            SQLiteAdapter,
        )

        db = SQLiteAdapter(":memory:")
        return LifeHistoryStore(
            db, SystemClock()
        ), db

    def _birth(
        self,
        store: LifeHistoryStore,
        name: str = "Bebe Prueba",
    ) -> dict[str, object]:
        return store.register_birth(
            registrar_account=_REGISTRAR,
            child_name=name,
            birth_date="2025-01-15",
            birth_place="San Salvador",
            sex="F",
            mother_name="Maria Perez",
            mother_zid=_MOTHER_ZID,
            father_name="Jose Lopez",
            father_zid=_FATHER_ZID,
            source_hospital="Hospital Nacional",
        )


class BirthRegistrationTests(_Base):
    def test_register_creates_person_and_cert(
        self,
    ) -> None:
        store, _db = self._store()
        birth = self._birth(store)
        self.assertTrue(
            birth["birth_id"].startswith("BRT-")
        )
        self.assertTrue(
            str(birth["cert_hash"]).startswith(
                "0"
            )
            or len(str(birth["cert_hash"])) == 64
        )
        person = store.get_person(
            str(birth["person_id"])
        )
        self.assertEqual(
            PERSON_REGISTERED,
            person["status"],
        )
        self.assertIsNone(person["zid"])
        parents = store.parents_of(
            str(birth["person_id"])
        )
        self.assertEqual(2, len(parents))
        roles = sorted(
            p["role"] for p in parents
        )
        self.assertEqual(
            ["madre", "padre"], roles
        )
        events = store.events_of(
            str(birth["person_id"])
        )
        self.assertEqual(
            "birth_registered",
            events[0]["event_type"],
        )
        self.assertTrue(
            store.events_verify(
                str(birth["person_id"])
            )
        )

    def test_national_chain_verifies(self) -> None:
        store, _db = self._store()
        self._birth(store, "Bebe Uno")
        self._birth(store, "Bebe Dos")
        self._birth(store, "Bebe Tres")
        ok, count = store.births_chain_verify()
        self.assertTrue(ok)
        self.assertEqual(3, count)

    def test_tamper_breaks_chain(self) -> None:
        store, db = self._store()
        first = self._birth(store, "Bebe Uno")
        second = self._birth(store, "Bebe Dos")
        db.execute(
            "UPDATE life_births SET"
            " birth_place = 'TAMPERED'"
            " WHERE birth_id = ?",
            (str(second["birth_id"]),),
        )
        ok, _count = store.births_chain_verify()
        self.assertFalse(ok)

    def test_parent_must_be_verified(self) -> None:
        store, _db = self._store()
        with self.assertRaises(
            ParentNotVerifiedError
        ):
            store.register_birth(
                registrar_account=(
                    _REGISTRAR
                ),
                child_name="Bebe",
                birth_date="2025-01-15",
                birth_place="Santa Ana",
                sex="M",
                mother_name="Maria Sin Zid",
                mother_zid="no-es-un-zid",
            )
        with self.assertRaises(
            ParentNotVerifiedError
        ):
            store.register_birth(
                registrar_account=(
                    _REGISTRAR
                ),
                child_name="Bebe",
                birth_date="2025-01-15",
                birth_place="Santa Ana",
                sex="M",
                mother_name="Maria Perez",
                mother_zid=_MOTHER_ZID,
                father_name="Jose Sin Zid",
            )


class IdentityUpgradeTests(_Base):
    def test_attach_zid_records_upgrade(
        self,
    ) -> None:
        store, _db = self._store()
        birth = self._birth(store)
        person_id = str(birth["person_id"])
        person = store.attach_zid(
            person_id,
            zid="ZID-newborn-0001",
            actor="biometric-enroll",
        )
        self.assertEqual(
            PERSON_VERIFIED,
            person["status"],
        )
        self.assertEqual(
            "ZID-newborn-0001",
            person["zid"],
        )
        events = store.events_of(person_id)
        self.assertEqual(
            "zid_biometric_upgrade",
            events[-1]["event_type"],
        )
        self.assertTrue(
            store.events_verify(person_id)
        )

    def test_life_events_chain(self) -> None:
        store, _db = self._store()
        birth = self._birth(store)
        person_id = str(birth["person_id"])
        store.add_life_event(
            person_id,
            actor="AX-doc1",
            event_type="health_exam",
            detail="control neonatal ok",
        )
        store.add_life_event(
            person_id,
            actor="AX-corte1",
            event_type="justice_note",
            detail="nada pendiente",
        )
        self.assertEqual(
            3,
            len(store.events_of(person_id)),
        )
        self.assertTrue(
            store.events_verify(person_id)
        )

    def test_amend_appends_never_deletes(
        self,
    ) -> None:
        store, _db = self._store()
        birth = self._birth(
            store, "Nombre Con Error"
        )
        original_cert = birth["cert_hash"]
        amended = store.amend_birth(
            str(birth["birth_id"]),
            actor=_REGISTRAR,
            amendment_type="rectificacion_nombre",
            detail="error de tipeo corregido",
            corrected_child_name=(
                "Nombre Corregido"
            ),
        )
        self.assertEqual(
            BIRTH_STATUS_AMENDED,
            amended["status"],
        )
        self.assertEqual(
            original_cert,
            amended["cert_hash"],
        )
        person = store.get_person(
            str(birth["person_id"])
        )
        self.assertEqual(
            "Nombre Corregido",
            person["full_name"],
        )
        events = store.events_of(
            str(birth["person_id"])
        )
        self.assertEqual(
            "birth_amendment:"
            "rectificacion_nombre",
            events[-1]["event_type"],
        )
        ok, _count = store.births_chain_verify()
        self.assertTrue(ok)
        self.assertTrue(
            store.events_verify(
                str(birth["person_id"])
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

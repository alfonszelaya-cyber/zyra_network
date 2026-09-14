"""AXIS Security x Life History - self-contained."""
from __future__ import annotations

import hashlib
import uuid

from apps.axis.life_history.service import (
    LifeHistoryService,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

INCIDENT_STAGES = (
    "reportado",
    "en_investigacion",
    "en_atencion",
    "resuelto",
    "archivado",
)

_MIGRATIONS = (
    Migration(
        1,
        "life_custody",
        (
            "CREATE TABLE IF NOT EXISTS life_custody ("
            " custody_id TEXT PRIMARY KEY,"
            " incident_id TEXT NOT NULL,"
            " previous_hash TEXT NOT NULL,"
            " event_hash TEXT NOT NULL,"
            " actor_zid TEXT NOT NULL,"
            " action TEXT NOT NULL,"
            " document_id TEXT,"
            " occurred_at REAL NOT NULL)",
        ),
    ),
)

GENESIS = "GENESIS"


def _sha256(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


class SecurityLifeService:
    def __init__(self, *, store, life=None):
        self._store = store
        self._life = life
        MigrationRunner(
            store._db,
            "axis.life_security",
            _MIGRATIONS,
        ).run(life._store._clock)

    def _person_for_account(self, account_id):
        if self._life is None:
            return None
        try:
            account = self._store.get_account(
                account_id
            )
        except LookupError:
            return None
        zid = account.get("zid")
        if not zid:
            return None
        row = self._life._store._db.query_one(
            "SELECT person_id FROM life_persons"
            " WHERE zid = ?",
            (str(zid),),
        )
        return (
            str(row["person_id"])
            if row is not None
            else None
        )

    def report_incident(
        self,
        *,
        incident_id,
        police_account,
        description,
        sealed_doc=None,
        subject_account=None,
    ):
        inc = self._store.add_incident(
            incident_id=incident_id,
            police_account=police_account,
            description=description,
            sealed_doc=sealed_doc,
        )
        person_id = None
        if subject_account:
            person_id = self._person_for_account(
                subject_account
            )
        chained = False
        if person_id is not None:
            try:
                self._life._store.add_life_event(
                    person_id,
                    actor=police_account,
                    event_type="security_incident",
                    detail=incident_id
                    + " [reportado]",
                )
                chained = True
            except Exception:
                chained = False
        return {
            **inc,
            "stage": "reportado",
            "subject_person_id": person_id,
            "life_chained": chained,
        }

    def advance_incident(
        self,
        *,
        incident_id,
        police_account,
        to_stage,
        note,
    ):
        if to_stage not in INCIDENT_STAGES:
            raise ValueError("bad stage")
        with self._store._db.transaction() as cursor:
            cursor.execute(
                "UPDATE axis_incidents SET"
                " description = ?"
                " WHERE incident_id = ?",
                (
                    "[" + to_stage + "] " + note,
                    incident_id,
                ),
            )
            if cursor.rowcount != 1:
                raise LookupError("unknown")
        person_id = self._incident_person(
            incident_id
        )
        chained = False
        if person_id is not None:
            try:
                self._life._store.add_life_event(
                    person_id,
                    actor=police_account,
                    event_type="security_status",
                    detail=incident_id
                    + " -> "
                    + to_stage,
                )
                chained = True
            except Exception:
                chained = False
        return {
            "incident_id": incident_id,
            "stage": to_stage,
            "life_chained": chained,
            "person_id": person_id,
        }

    def add_custody(
        self,
        *,
        incident_id,
        actor_zid,
        action,
        document_id=None,
    ):
        now = self._life._store._clock.now()
        with self._store._db.transaction() as cursor:
            row = cursor.execute(
                "SELECT event_hash FROM life_custody"
                " WHERE incident_id = ?"
                " ORDER BY rowid DESC LIMIT 1",
                (incident_id,),
            ).fetchone()
            previous = (
                str(row["event_hash"])
                if row is not None
                else GENESIS
            )
            event_hash = _sha256(
                "|".join(
                    (
                        incident_id,
                        previous,
                        actor_zid,
                        action,
                        document_id or "",
                        str(now),
                    )
                )
            )
            custody_id = (
                "LCU-" + uuid.uuid4().hex[:10]
            )
            cursor.execute(
                "INSERT INTO life_custody ("
                " custody_id, incident_id,"
                " previous_hash, event_hash,"
                " actor_zid, action,"
                " document_id, occurred_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    custody_id,
                    incident_id,
                    previous,
                    event_hash,
                    actor_zid,
                    action,
                    document_id,
                    now,
                ),
            )
        return {
            "custody_id": custody_id,
            "chain_valid": self.custody_verified(
                incident_id
            ),
        }

    def custody_verified(self, incident_id):
        rows = self._store._db.query_all(
            "SELECT * FROM life_custody"
            " WHERE incident_id = ?"
            " ORDER BY rowid",
            (incident_id,),
        )
        previous = GENESIS
        for row in rows:
            expected = _sha256(
                "|".join(
                    (
                        str(row["incident_id"]),
                        previous,
                        str(row["actor_zid"]),
                        str(row["action"]),
                        (
                            str(row["document_id"])
                            if row["document_id"]
                            is not None
                            else ""
                        ),
                        str(row["occurred_at"]),
                    )
                )
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

    def incident_status(self, incident_id):
        row = self._store._db.query_one(
            "SELECT description FROM axis_incidents"
            " WHERE incident_id = ?",
            (incident_id,),
        )
        description = (
            str(row["description"])
            if row is not None
            else None
        )
        stage = "reportado"
        if description and description.startswith(
            "["
        ):
            stage = description.split("]")[0][1:]
        return {
            "incident_id": incident_id,
            "stage": stage,
            "description": description,
            "custody_verified": (
                self.custody_verified(incident_id)
            ),
        }

    def _incident_person(self, incident_id):
        row = self._life._store._db.query_one(
            "SELECT person_id FROM life_events"
            " WHERE event_type ="
            " 'security_incident' AND detail"
            " LIKE ? ORDER BY occurred_at DESC"
            " LIMIT 1",
            (incident_id + "%",),
        )
        return (
            str(row["person_id"])
            if row is not None
            else None
        )

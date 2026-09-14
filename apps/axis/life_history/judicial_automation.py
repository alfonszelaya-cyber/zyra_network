"""AXIS Judicial automation - complete."""
import hashlib
import uuid

from apps.axis.life_history.access_control import (
    authorize,
)

BRANCHES = {
    "penal": {
        "evidence_required": True,
        "sentencer": ("juez_penal", "gobierno"),
    },
    "civil": {
        "evidence_required": False,
        "sentencer": ("juez_civil", "gobierno"),
    },
    "familiar": {
        "evidence_required": False,
        "sentencer": ("juez_familiar", "gobierno"),
    },
    "laboral": {
        "evidence_required": False,
        "sentencer": ("juez_laboral", "gobierno"),
    },
    "comercial": {
        "evidence_required": False,
        "sentencer": ("juez_comercial", "gobierno"),
    },
    "administrativo": {
        "evidence_required": False,
        "sentencer": ("gobierno",),
    },
}

START_STAGES = {
    "penal": "denuncia",
    "civil": "demanda",
    "familiar": "demanda",
    "laboral": "demanda",
    "comercial": "demanda",
    "administrativo": "recurso",
}


class JudicialAutomationError(Exception):
    pass


class JudicialAutomation:
    def __init__(self, *, life, db):
        self._life = life
        self._db = db
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS"
            " judicial_cases ("
            " case_id TEXT PRIMARY KEY,"
            " person_id TEXT NOT NULL,"
            " branch TEXT NOT NULL,"
            " stage TEXT NOT NULL,"
            " actor TEXT NOT NULL,"
            " created_at REAL NOT NULL,"
            " updated_at REAL NOT NULL)"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS"
            " judicial_evidence ("
            " evidence_id TEXT PRIMARY KEY,"
            " case_id TEXT NOT NULL,"
            " description TEXT NOT NULL,"
            " sealed_doc TEXT,"
            " created_at REAL NOT NULL)"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS"
            " judicial_audiencias ("
            " audiencia_id TEXT PRIMARY KEY,"
            " case_id TEXT NOT NULL,"
            " scheduled_at TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at REAL NOT NULL)"
        )

    def open_case(
        self, *, case_id, person_id,
        branch, actor, actor_role,
        detail,
    ):
        if branch not in BRANCHES:
            raise (
                JudicialAutomationError(
                    "unknown branch: "
                    + str(branch)
                )
            )
        if not authorize(
            "justice.case", actor_role
        ):
            raise (
                JudicialAutomationError(
                    "role not authorized"
                )
            )
        now = (
            self._life._store._clock.now()
        )
        start = START_STAGES[branch]
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO judicial_cases"
                " (case_id, person_id,"
                " branch, stage, actor,"
                " created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    case_id,
                    person_id,
                    branch,
                    start,
                    actor,
                    now,
                    now,
                ),
            )
            self._chain_event(
                cursor,
                person_id=person_id,
                actor=actor,
                event_type=(
                    "justice_case"
                ),
                detail=case_id
                + " abierto ["
                + branch
                + "]",
                now=now,
            )
        return self.get_case(case_id)

    def add_evidence(
        self, *, case_id, actor,
        actor_role, description,
        sealed_doc=None,
    ):
        if not authorize(
            "justice.case", actor_role
        ):
            raise (
                JudicialAutomationError(
                    "not authorized"
                )
            )
        case = self.get_case(case_id)
        if case is None:
            raise (
                JudicialAutomationError(
                    "unknown case"
                )
            )
        now = (
            self._life._store._clock.now()
        )
        eid = (
            "EVD-"
            + uuid.uuid4().hex[:10]
        )
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " judicial_evidence ("
                " evidence_id, case_id,"
                " description, sealed_doc,"
                " created_at)"
                " VALUES (?,?,?,?,?)",
                (
                    eid,
                    case_id,
                    description,
                    sealed_doc,
                    now,
                ),
            )
            self._chain_event(
                cursor,
                person_id=str(
                    case["person_id"]
                ),
                actor=actor,
                event_type=(
                    "justice_evidence"
                ),
                detail=eid
                + ": "
                + description[:40],
                now=now,
            )
        return {"evidence_id": eid}

    def schedule_audiencia(
        self, *, case_id, actor,
        actor_role, scheduled_at,
    ):
        case = self.get_case(case_id)
        if case is None:
            raise (
                JudicialAutomationError(
                    "unknown case"
                )
            )
        cfg = BRANCHES[
            str(case["branch"])
        ]
        if cfg["evidence_required"]:
            ev = self._db.query_one(
                "SELECT 1 FROM"
                " judicial_evidence"
                " WHERE case_id = ?",
                (case_id,),
            )
            if ev is None:
                raise (
                    JudicialAutomationError(
                        "evidence required"
                        " before audiencia"
                    )
                )
        now = (
            self._life._store._clock.now()
        )
        aid = (
            "AUD-"
            + uuid.uuid4().hex[:10]
        )
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " judicial_audiencias ("
                " audiencia_id, case_id,"
                " scheduled_at, status,"
                " created_at)"
                " VALUES (?,?,?,?,?)",
                (
                    aid,
                    case_id,
                    scheduled_at,
                    "programada",
                    now,
                ),
            )
            self._advance_stage(
                cursor,
                case_id=case_id,
                stage="audiencia",
                actor=actor,
                now=now,
            )
        return {"audiencia_id": aid}

    def sentence(
        self, *, case_id, actor,
        actor_role, verdict,
    ):
        case = self.get_case(case_id)
        if case is None:
            raise (
                JudicialAutomationError(
                    "unknown case"
                )
            )
        cfg = BRANCHES[
            str(case["branch"])
        ]
        if actor_role not in cfg[
            "sentencer"
        ]:
            raise (
                JudicialAutomationError(
                    "role cannot sentence:"
                    " " + actor_role
                )
            )
        now = (
            self._life._store._clock.now()
        )
        with self._db.transaction() as cursor:
            self._advance_stage(
                cursor,
                case_id=case_id,
                stage="sentencia",
                actor=actor,
                now=now,
            )
            self._chain_event(
                cursor,
                person_id=str(
                    case["person_id"]
                ),
                actor=actor,
                event_type=(
                    "justice_status"
                ),
                detail=case_id
                + " sentencia: "
                + verdict[:60],
                now=now,
            )
        return {"sentenced": True}

    def close_case(
        self, *, case_id, actor,
    ):
        now = (
            self._life._store._clock.now()
        )
        with self._db.transaction() as cursor:
            self._advance_stage(
                cursor,
                case_id=case_id,
                stage="cerrado",
                actor=actor,
                now=now,
            )
        return {"closed": True}

    def _advance_stage(
        self, cursor, *, case_id,
        stage, actor, now,
    ):
        cursor.execute(
            "UPDATE judicial_cases SET"
            " stage = ?, updated_at = ?"
            " WHERE case_id = ?",
            (stage, now, case_id),
        )
        row = cursor.execute(
            "SELECT person_id FROM"
            " judicial_cases WHERE"
            " case_id = ?",
            (case_id,),
        ).fetchone()
        if row is not None:
            self._chain_event(
                cursor,
                person_id=str(
                    row["person_id"]
                ),
                actor=actor,
                event_type=(
                    "justice_status"
                ),
                detail=case_id
                + " -> "
                + stage,
                now=now,
            )

    def _chain_event(
        self, cursor, *, person_id,
        actor, event_type, detail,
        now,
    ):
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
            else "GENESIS"
        )
        payload = "|".join(
            (
                person_id,
                previous,
                actor,
                event_type,
                detail or "",
                str(now),
            )
        )
        event_hash = hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()
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
            " VALUES (?,?,?,?,?,?,?,?)",
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
            "event_id": event_id
        }

    def get_case(self, case_id):
        row = self._db.query_one(
            "SELECT * FROM judicial_cases"
            " WHERE case_id = ?",
            (case_id,),
        )
        if row is None:
            return None
        return {
            "case_id": str(
                row["case_id"]
            ),
            "person_id": str(
                row["person_id"]
            ),
            "branch": str(
                row["branch"]
            ),
            "stage": str(
                row["stage"]
            ),
        }

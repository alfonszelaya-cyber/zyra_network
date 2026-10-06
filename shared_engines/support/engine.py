
"""Motor TRANSVERSAL de atencion al cliente.

Sirve a TODAS las apps de la Red (NEXO, SUBASTAS,
AGRO, AXIS, SEMILLA, MPE...). Cada ticket lleva
app_id para saber de donde viene. Escalamiento
global cross-app: un caso puede cruzar apps
(NEXO+AXIS, NEXO+SEMILLA...) como el Modulo 10
del viejo diseno. La Red transporta el ticket;
las apps tienen sus agentes."""
from __future__ import annotations

from typing import Dict, List, Optional
import uuid

from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

TICKET_PRIORITIES = ("LOW", "NORMAL", "HIGH", "CRITICAL")
TICKET_STATUSES = ("OPEN", "ASSIGNED", "IN_PROGRESS",
                   "ESCALATED", "RESOLVED", "CLOSED")
APP_IDS = ("nexo", "subastas", "agro", "axis",
           "semilla", "mpe", "futuro", "lab", "global")

_MIGRATIONS = (
    Migration(1, "support_tickets", (
        "CREATE TABLE IF NOT EXISTS support_tickets (ticket_id TEXT PRIMARY KEY, app_id TEXT NOT NULL, client_id TEXT NOT NULL DEFAULT '', title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', priority TEXT NOT NULL DEFAULT 'NORMAL', status TEXT NOT NULL DEFAULT 'OPEN', agent_id TEXT, resolution TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
    Migration(2, "support_escalations", (
        "CREATE TABLE IF NOT EXISTS support_escalations (escalation_id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL, from_app TEXT NOT NULL, to_app TEXT NOT NULL, level TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
    Migration(3, "support_feedback", (
        "CREATE TABLE IF NOT EXISTS support_feedback (feedback_id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL, client_id TEXT NOT NULL, score INTEGER NOT NULL, comments TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
    Migration(4, "support_cases", (
        "CREATE TABLE IF NOT EXISTS support_cases (case_id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL, apps_involved_json TEXT NOT NULL DEFAULT '[]', case_data_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN', created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
)


class SupportEngine:
    """Motor transversal de atencion al cliente."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "support.core",
                        _MIGRATIONS).run(clock)

    # ---------- TICKETS ----------
    def create_ticket(self, *, app_id: str, title: str,
                      description: str = "",
                      client_id: str = "",
                      priority: str = "NORMAL") -> dict:
        if app_id not in APP_IDS:
            app_id = "global"
        if priority not in TICKET_PRIORITIES:
            priority = "NORMAL"
        ticket_id = "TKT-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO support_tickets"
                " (ticket_id, app_id, client_id, title,"
                " description, priority, status, agent_id,"
                " resolution, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 'OPEN',"
                " NULL, NULL, ?, ?)",
                (ticket_id, app_id, client_id, title,
                 description, priority, now, now))
        return self.get_ticket(ticket_id)

    def get_ticket(self, ticket_id: str) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM support_tickets"
            " WHERE ticket_id = ?", (ticket_id,))
        return self._ticket_row(row) if row else None

    def _ticket_row(self, row) -> dict:
        return {"ticket_id": str(row["ticket_id"]),
                "app_id": str(row["app_id"]),
                "client_id": str(row["client_id"]),
                "title": str(row["title"]),
                "description": str(row["description"]),
                "priority": str(row["priority"]),
                "status": str(row["status"]),
                "agent_id": (str(row["agent_id"])
                             if row["agent_id"] else None),
                "resolution": (str(row["resolution"])
                               if row["resolution"] else None),
                "created_at": float(row["created_at"]),
                "updated_at": float(row["updated_at"])}

    def assign_ticket(self, *, ticket_id: str,
                      agent_id: str) -> dict:
        row = self._db.query_one(
            "SELECT status FROM support_tickets"
            " WHERE ticket_id = ?", (ticket_id,))
        if not row:
            raise KeyError(ticket_id)
        self._db.execute(
            "UPDATE support_tickets SET"
            " status = 'ASSIGNED', agent_id = ?,"
            " updated_at = ? WHERE ticket_id = ?",
            (agent_id, self._clock.now(), ticket_id))
        return self.get_ticket(ticket_id)

    def escalate_ticket(self, *, ticket_id: str,
                        to_app: str, level: str = "HIGH",
                        reason: str = "") -> dict:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            raise KeyError(ticket_id)
        esc_id = "ESC-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO support_escalations"
                " (escalation_id, ticket_id, from_app,"
                " to_app, level, reason, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (esc_id, ticket_id, ticket["app_id"],
                 to_app, level, reason, now))
            cursor.execute(
                "UPDATE support_tickets SET"
                " status = 'ESCALATED', updated_at = ?"
                " WHERE ticket_id = ?",
                (now, ticket_id))
        return {"escalation_id": esc_id,
                "ticket_id": ticket_id,
                "from_app": ticket["app_id"],
                "to_app": to_app, "level": level,
                "reason": reason,
                "status": "ESCALATED"}

    def resolve_ticket(self, *, ticket_id: str,
                       resolution: str) -> dict:
        now = self._clock.now()
        self._db.execute(
            "UPDATE support_tickets SET"
            " status = 'RESOLVED', resolution = ?,"
            " updated_at = ? WHERE ticket_id = ?",
            (resolution, now, ticket_id))
        return self.get_ticket(ticket_id)

    def close_ticket(self, *, ticket_id: str) -> dict:
        now = self._clock.now()
        self._db.execute(
            "UPDATE support_tickets SET"
            " status = 'CLOSED', updated_at = ?"
            " WHERE ticket_id = ?",
            (now, ticket_id))
        return self.get_ticket(ticket_id)

    def get_tickets_by_app(self, app_id: str) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM support_tickets"
            " WHERE app_id = ? ORDER BY created_at DESC"
            " LIMIT 200", (app_id,))
        return [self._ticket_row(r) for r in rows]

    def get_open_tickets(self, app_id: str = "") -> List[dict]:
        if app_id:
            rows = self._db.query_all(
                "SELECT * FROM support_tickets"
                " WHERE app_id = ? AND status IN"
                " ('OPEN','ASSIGNED','IN_PROGRESS',"
                " 'ESCALATED')"
                " ORDER BY created_at DESC LIMIT 100",
                (app_id,))
        else:
            rows = self._db.query_all(
                "SELECT * FROM support_tickets"
                " WHERE status IN ('OPEN','ASSIGNED',"
                " 'IN_PROGRESS','ESCALATED')"
                " ORDER BY created_at DESC LIMIT 100")
        return [self._ticket_row(r) for r in rows]

    # ---------- CASOS TRANSVERSALES ----------
    def create_cross_app_case(self, *, apps_involved,
                              title: str, case_data=None) -> dict:
        """Caso que cruza varias apps
        (ej: NEXO+AXIS, NEXO+SEMILLA)."""
        case_id = "CAS-" + str(uuid.uuid4())
        now = self._clock.now()
        import json as _j
        ticket = self.create_ticket(
            app_id="global", title=title,
            description="caso transversal: "
            + ", ".join(apps_involved),
            priority="HIGH")
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO support_cases"
                " (case_id, ticket_id,"
                " apps_involved_json,"
                " case_data_json, status,"
                " created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 'OPEN', ?, ?)",
                (case_id, ticket["ticket_id"],
                 _j.dumps(apps_involved, default=str),
                 _j.dumps(case_data or {},
                          default=str), now, now))
        return {"case_id": case_id,
                "ticket_id": ticket["ticket_id"],
                "apps_involved": apps_involved,
                "title": title,
                "status": "OPEN"}

    # ---------- FEEDBACK ----------
    def register_feedback(self, *, ticket_id: str,
                          client_id: str, score: int,
                          comments: str = "") -> dict:
        if score < 1:
            score = 1
        if score > 10:
            score = 10
        feedback_id = "FDB-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO support_feedback"
                " (feedback_id, ticket_id, client_id,"
                " score, comments, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (feedback_id, ticket_id, client_id,
                 score, comments, now))
        return {"feedback_id": feedback_id,
                "ticket_id": ticket_id,
                "client_id": client_id,
                "score": score,
                "status": "REGISTERED"}

    def average_satisfaction(self, app_id: str = "") -> dict:
        if app_id:
            tickets = self.get_tickets_by_app(app_id)
            tids = [t["ticket_id"] for t in tickets]
            if not tids:
                return {"score": 0, "responses": 0}
            marks = []
            for tid in tids:
                rows = self._db.query_all(
                    "SELECT score FROM support_feedback"
                    " WHERE ticket_id = ?", (tid,))
                marks.extend([int(r["score"])
                              for r in rows])
        else:
            rows = self._db.query_all(
                "SELECT score FROM support_feedback")
            marks = [int(r["score"]) for r in rows]
        if not marks:
            return {"score": 0, "responses": 0}
        return {"score": round(sum(marks)
                               / len(marks), 2),
                "responses": len(marks)}

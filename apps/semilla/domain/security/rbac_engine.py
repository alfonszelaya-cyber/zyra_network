
"""RBAC Engine SEMILLA - 6 roles (SM9, SE-3).
STUDENT/PARENT/TEACHER/DIRECTOR/GOVERNMENT/COMPANY
con permisos por accion. Asignacion persistente y
verificacion can()."""
from __future__ import annotations
from typing import Dict, List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

ROLES = ("STUDENT", "PARENT", "TEACHER",
         "DIRECTOR", "GOVERNMENT", "COMPANY")

PERMISSIONS = {
    "STUDENT": ("READ_OWN", "USE_TUTOR",
                "VIEW_OWN_GRADES",
                "APPLY_SCHOLARSHIP"),
    "PARENT": ("READ_CHILD", "VIEW_CHILD_GRADES",
               "GRANT_CONSENT", "PAY_FEES",
               "VIEW_ALERTS"),
    "TEACHER": ("READ_STUDENT", "WRITE_GRADES",
                "TAKE_ATTENDANCE",
                "REPORT_INCIDENT",
                "VIEW_INSIGHTS"),
    "DIRECTOR": ("READ_STUDENT", "WRITE_GRADES",
                 "TAKE_ATTENDANCE",
                 "REPORT_INCIDENT",
                 "MANAGE_SCHOOL",
                 "ENROLL_STUDENT",
                 "VIEW_INSIGHTS",
                 "VERIFY_INSTITUTION"),
    "GOVERNMENT": ("VIEW_NATIONAL",
                   "SUPERVISE_SCHOOL",
                   "READ_AGGREGATE",
                   "VERIFY_MINED"),
    "COMPANY": ("VIEW_ANON_OFFERS",),
}

_MIGRATIONS = (
    Migration(1, "sm_rbac_assignments", (
        "CREATE TABLE IF NOT EXISTS sm_rbac_assignments (assignment_id TEXT PRIMARY KEY, actor TEXT NOT NULL, role TEXT NOT NULL, institution_id TEXT NOT NULL DEFAULT '', student_scope TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL)",
    )),
)

class RbacEngine:
    """Roles y permisos SEMILLA (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.rbac",
                        _MIGRATIONS).run(clock)

    def assign(self, *, actor, role,
               institution_id="",
               student_scope="") -> dict:
        if role not in ROLES:
            raise ValueError(
                "rol invalido: " + str(role))
        aid = "SMRB-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_rbac_assignments"
                " (assignment_id, actor, role,"
                " institution_id, student_scope,"
                " active, created_at)"
                " VALUES (?, ?, ?, ?, ?, 1, ?)",
                (aid, str(actor), role,
                 str(institution_id),
                 str(student_scope), now))
        return self.get_assignment(aid)

    def get_assignment(self, assignment_id
                       ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_rbac_assignments"
            " WHERE assignment_id = ?",
            (assignment_id,))
        if not row:
            return None
        return {"assignment_id":
                    str(row["assignment_id"]),
                "actor": str(row["actor"]),
                "role": str(row["role"]),
                "institution_id":
                    str(row["institution_id"]),
                "student_scope":
                    str(row["student_scope"]),
                "active": bool(row["active"])}

    def revoke(self, assignment_id) -> dict:
        self._db.execute(
            "UPDATE sm_rbac_assignments SET"
            " active = 0 WHERE assignment_id"
            " = ?", (assignment_id,))
        return self.get_assignment(
            assignment_id)

    def role_of(self, actor) -> Optional[str]:
        row = self._db.query_one(
            "SELECT role FROM"
            " sm_rbac_assignments WHERE"
            " actor = ? AND active = 1 ORDER BY"
            " rowid DESC LIMIT 1", (actor,))
        return (str(row["role"])
                if row else None)

    def can(self, *, actor, action) -> dict:
        role = self.role_of(actor)
        if role is None:
            return {"allowed": False,
                    "reason": "sin rol asignado"}
        perms = PERMISSIONS.get(role, ())
        if action not in perms:
            return {"allowed": False,
                    "reason": ("rol " + role
                               + " no puede "
                               + action)}
        return {"allowed": True,
                "reason": "ok",
                "role": role}

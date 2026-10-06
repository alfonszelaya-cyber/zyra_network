
"""Laboratory Engine - proyectos y experimentos de
laboratorios escolares (SM7). 9 labs. Produccion
real persistente."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

LAB_TYPES = ("AI", "ROBOTICS", "PROGRAMMING",
             "BIOTECH", "ENERGY", "AEROSPACE",
             "QUANTUM", "NANO", "CYBERSECURITY")

_MIGRATIONS = (
    Migration(1, "sm_lab_projects", (
        "CREATE TABLE IF NOT EXISTS sm_lab_projects (project_id TEXT PRIMARY KEY, lab_type TEXT NOT NULL, title TEXT NOT NULL, lead_student_id TEXT NOT NULL, members_json TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'ACTIVE', created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
    Migration(2, "sm_lab_experiments", (
        "CREATE TABLE IF NOT EXISTS sm_lab_experiments (experiment_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL, method TEXT NOT NULL DEFAULT '', result TEXT, success INTEGER, created_at REAL NOT NULL)",
    )),
)

class LaboratoryEngine:
    """Proyectos y experimentos de laboratorio."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.lab",
                        _MIGRATIONS).run(clock)

    def create_project(self, *, lab_type, title,
                       lead_student_id,
                       members=None) -> dict:
        if lab_type not in LAB_TYPES:
            raise ValueError("lab_type invalido: "
                             + str(lab_type))
        if not str(title).strip():
            raise ValueError("title requerido")
        pid = "SMLAB-" + str(uuid.uuid4())
        now = self._clock.now()
        import json as _j
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_lab_projects"
                " (project_id, lab_type, title,"
                " lead_student_id, members_json,"
                " status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, 'ACTIVE',"
                " ?, ?)",
                (pid, lab_type,
                 str(title).strip(),
                 lead_student_id,
                 _j.dumps(members or [],
                          default=str), now, now))
        return self.get_project(pid)

    def get_project(self, project_id
                    ) -> Optional[dict]:
        import json as _j
        row = self._db.query_one(
            "SELECT * FROM sm_lab_projects WHERE"
            " project_id = ?", (project_id,))
        if not row:
            return None
        return {"project_id":
                    str(row["project_id"]),
                "lab_type": str(row["lab_type"]),
                "title": str(row["title"]),
                "lead_student_id":
                    str(row["lead_student_id"]),
                "members": _j.loads(
                    str(row["members_json"])),
                "status": str(row["status"])}

    def run_experiment(self, *, project_id, name,
                       method="",
                       result=None,
                       success=None) -> dict:
        p = self.get_project(project_id)
        if not p:
            raise KeyError(project_id)
        if p["status"] != "ACTIVE":
            raise ValueError(
                "proyecto no activo")
        if not str(name).strip():
            raise ValueError("name requerido")
        eid = "SMEXP-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_lab_experiments"
                " (experiment_id, project_id,"
                " name, method, result, success,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (eid, project_id,
                 str(name).strip(),
                 str(method),
                 (str(result) if result
                  is not None else None),
                 (1 if success else 0
                  if success is not None
                  else None), now))
        return {"experiment_id": eid,
                "project_id": project_id,
                "name": str(name).strip()}

    def complete_project(self, project_id) -> dict:
        self._db.execute(
            "UPDATE sm_lab_projects SET status ="
            " 'COMPLETED', updated_at = ? WHERE"
            " project_id = ?",
            (self._clock.now(), project_id))
        return self.get_project(project_id)

    def experiments_of(self, project_id
                       ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM sm_lab_experiments"
            " WHERE project_id = ? ORDER BY rowid",
            (project_id,))
        return [{"experiment_id":
                     str(r["experiment_id"]),
                 "name": str(r["name"]),
                 "method": str(r["method"]),
                 "result": (str(r["result"])
                            if r["result"]
                            else None),
                 "success": (bool(r["success"])
                             if r["success"]
                             is not None
                             else None)}
                for r in rows]

    def projects_by_lab(self,
                        lab_type) -> List[dict]:
        rows = self._db.query_all(
            "SELECT project_id FROM"
            " sm_lab_projects WHERE lab_type = ?"
            " ORDER BY created_at", (lab_type,))
        return [self.get_project(
            str(r["project_id"]))
            for r in rows]

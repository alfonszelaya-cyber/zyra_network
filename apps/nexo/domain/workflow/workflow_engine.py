
"""Nexo Workflow Engine - flujos con estados estrictos
(NG7). Persistente."""
from __future__ import annotations
from typing import List, Optional
import json as _j
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)
from apps.nexo.domain.workflow.workflow_state import (
    assert_transition)

_MIGRATIONS = (
    Migration(1, "nexo_workflow_defs", (
        "CREATE TABLE IF NOT EXISTS nexo_workflow_defs (workflow_id TEXT PRIMARY KEY, name TEXT NOT NULL, steps_json TEXT NOT NULL DEFAULT '[]', active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL)",
    )),
    Migration(2, "nexo_workflow_runs", (
        "CREATE TABLE IF NOT EXISTS nexo_workflow_runs (run_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, current_step INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'CREATED', payload_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
)

class NexoWorkflowEngine:
    """Workflows con pasos y estados."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.wf",
                        _MIGRATIONS).run(clock)

    def create_workflow(self, *, name,
                        steps) -> dict:
        names = [str(s).strip() for s in steps]
        if not names or any(
                not n for n in names):
            raise ValueError(
                "steps invalidos")
        if len(set(names)) != len(names):
            raise ValueError(
                "pasos duplicados")
        wid = "WF-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_workflow_defs"
                " (workflow_id, name, steps_json,"
                " active, created_at)"
                " VALUES (?, ?, ?, 1, ?)",
                (wid, name,
                 _j.dumps(names), now))
        return {"workflow_id": wid,
                "name": name,
                "steps": names,
                "active": True}

    def get_workflow(self,
                     workflow_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_workflow_defs"
            " WHERE workflow_id = ?",
            (workflow_id,))
        if not row:
            return None
        return {"workflow_id":
                    str(row["workflow_id"]),
                "name": str(row["name"]),
                "steps": _j.loads(
                    str(row["steps_json"])),
                "active": bool(row["active"])}

    def start_run(self, *, workflow_id,
                  payload=None) -> dict:
        wf = self.get_workflow(workflow_id)
        if not wf or not wf["active"]:
            raise ValueError(
                "workflow inexistente/inactivo")
        rid = "RUN-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_workflow_runs"
                " (run_id, workflow_id,"
                " current_step, status,"
                " payload_json, created_at,"
                " updated_at)"
                " VALUES (?, ?, 0, 'CREATED', ?,"
                " ?, ?)",
                (rid, workflow_id,
                 _j.dumps(payload or {},
                          default=str), now, now))
        return self.get_run(rid)

    def get_run(self,
                run_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_workflow_runs"
            " WHERE run_id = ?", (run_id,))
        if not row:
            return None
        wf = self.get_workflow(
            str(row["workflow_id"]))
        step = int(row["current_step"])
        return {"run_id": str(row["run_id"]),
                "workflow_id":
                    str(row["workflow_id"]),
                "current_step": step,
                "current_step_name": (
                    wf["steps"][step]
                    if wf and step
                    < len(wf["steps"]) else None),
                "steps_total": (len(wf["steps"])
                                if wf else 0),
                "status": str(row["status"]),
                "payload": _j.loads(
                    str(row["payload_json"])),
                "updated_at":
                    float(row["updated_at"])}

    def _set(self, run_id, status, step=None):
        now = self._clock.now()
        if step is None:
            self._db.execute(
                "UPDATE nexo_workflow_runs SET"
                " status = ?, updated_at = ?"
                " WHERE run_id = ?",
                (status, now, run_id))
        else:
            self._db.execute(
                "UPDATE nexo_workflow_runs SET"
                " status = ?, current_step = ?,"
                " updated_at = ? WHERE run_id = ?",
                (status, step, now, run_id))
        return self.get_run(run_id)

    def _status(self, run_id) -> str:
        row = self._db.query_one(
            "SELECT status FROM"
            " nexo_workflow_runs WHERE"
            " run_id = ?", (run_id,))
        if not row:
            raise KeyError(run_id)
        return str(row["status"])

    def start(self, run_id) -> dict:
        assert_transition(self._status(run_id),
                          "RUNNING")
        return self._set(run_id, "RUNNING")

    def advance(self, run_id) -> dict:
        if self._status(run_id) != "RUNNING":
            raise ValueError(
                "solo RUNNING avanza")
        run = self.get_run(run_id)
        nxt = run["current_step"] + 1
        if nxt >= run["steps_total"]:
            return self._set(run_id, "COMPLETED",
                             nxt)
        return self._set(run_id, "RUNNING",
                         nxt)

    def pause(self, run_id) -> dict:
        assert_transition(
            self._status(run_id), "PAUSED")
        return self._set(run_id, "PAUSED")

    def resume(self, run_id) -> dict:
        assert_transition(
            self._status(run_id), "RUNNING")
        return self._set(run_id, "RUNNING")

    def cancel(self, run_id) -> dict:
        assert_transition(
            self._status(run_id), "CANCELLED")
        return self._set(run_id, "CANCELLED")

    def fail(self, run_id, detail="") -> dict:
        assert_transition(
            self._status(run_id), "FAILED")
        return self._set(run_id, "FAILED")

    def runs_of(self, workflow_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT run_id FROM"
            " nexo_workflow_runs WHERE"
            " workflow_id = ?"
            " ORDER BY created_at",
            (workflow_id,))
        return [self.get_run(
            str(r["run_id"])) for r in rows]

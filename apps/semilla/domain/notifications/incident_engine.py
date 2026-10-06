
"""Incident Engine - incidencias (SM1)."""
from __future__ import annotations
from typing import List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

INCIDENT_TYPES = ("BEHAVIOR", "HEALTH",
                  "PERMISSION_EXIT", "GENERAL")
SEVERITIES = ("LOW", "MEDIUM", "HIGH")

_MIGRATIONS = (
    Migration(1, "sm_incidents", (
        "CREATE TABLE IF NOT EXISTS sm_incidents (incident_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, incident_type TEXT NOT NULL, severity TEXT NOT NULL DEFAULT 'LOW', detail TEXT NOT NULL DEFAULT '', reported_by TEXT NOT NULL DEFAULT '', resolution TEXT, resolved INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, resolved_at REAL)",
    )),
)

class IncidentEngine:
    """Incidencias con aviso al encargado."""

    def __init__(self, db, clock,
                 alert_engine=None):
        self._db = db
        self._clock = clock
        self._alerts = alert_engine
        MigrationRunner(db, "sm.incidents",
                        _MIGRATIONS).run(clock)

    def report(self, *, student_id, incident_type,
               detail, severity="LOW",
               reported_by="") -> dict:
        if incident_type not in INCIDENT_TYPES:
            raise ValueError(
                "tipo de incidencia invalido")
        if severity not in SEVERITIES:
            severity = "LOW"
        iid = "SMINC-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_incidents"
                " (incident_id, student_id,"
                " incident_type, severity,"
                " detail, reported_by, resolved,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                (iid, student_id, incident_type,
                 severity, str(detail),
                 str(reported_by), now))
        if self._alerts is not None:
            tmap = {"BEHAVIOR":
                    "Incidencia de conducta",
                    "HEALTH":
                    "Incidencia de salud",
                    "PERMISSION_EXIT":
                    "Permiso de salida",
                    "GENERAL":
                    "Incidencia escolar"}
            self._alerts.publish(
                student_id=student_id,
                alert_type=(
                    "HEALTH" if incident_type
                    == "HEALTH" else
                    "BEHAVIOR" if incident_type
                    == "BEHAVIOR" else "GENERAL"),
                title=tmap[incident_type],
                detail=str(detail),
                recipient_role="PARENT")
        return {"incident_id": iid,
                "student_id": student_id,
                "incident_type": incident_type,
                "severity": severity,
                "parent_notified":
                    self._alerts is not None}

    def resolve(self, incident_id,
                resolution) -> dict:
        self._db.execute(
            "UPDATE sm_incidents SET resolved = 1,"
            " resolution = ?, resolved_at = ?"
            " WHERE incident_id = ?",
            (str(resolution),
             self._clock.now(), incident_id))
        row = self._db.query_one(
            "SELECT * FROM sm_incidents WHERE"
            " incident_id = ?", (incident_id,))
        if not row:
            raise KeyError(incident_id)
        return {"incident_id":
                    str(row["incident_id"]),
                "resolved": True}

    def incidents_of(self, student_id
                     ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM sm_incidents WHERE"
            " student_id = ? ORDER BY"
            " created_at", (student_id,))
        return [{"incident_id":
                     str(r["incident_id"]),
                 "incident_type":
                     str(r["incident_type"]),
                 "severity":
                     str(r["severity"]),
                 "detail": str(r["detail"]),
                 "resolved":
                     bool(r["resolved"])}
                for r in rows]

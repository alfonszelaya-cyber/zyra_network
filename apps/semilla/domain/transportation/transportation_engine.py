
"""Transportation Engine - transporte escolar
(SM8). Rutas/paradas/estudiantes con cupos."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sm_transport_routes", (
        "CREATE TABLE IF NOT EXISTS sm_transport_routes (route_id TEXT PRIMARY KEY, name TEXT NOT NULL, driver TEXT NOT NULL DEFAULT '', capacity INTEGER NOT NULL DEFAULT 20, assigned INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL)",
    )),
    Migration(2, "sm_transport_stops", (
        "CREATE TABLE IF NOT EXISTS sm_transport_stops (stop_id TEXT PRIMARY KEY, route_id TEXT NOT NULL, stop_name TEXT NOT NULL, order_num INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL)",
    )),
    Migration(3, "sm_transport_students", (
        "CREATE TABLE IF NOT EXISTS sm_transport_students (assign_id TEXT PRIMARY KEY, route_id TEXT NOT NULL, student_id TEXT NOT NULL, stop_id TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, UNIQUE(student_id))",
    )),
)

class TransportationEngine:
    """Rutas de transporte escolar (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.transport",
                        _MIGRATIONS).run(clock)

    def create_route(self, *, name, driver="",
                     capacity=20) -> dict:
        if not str(name).strip():
            raise ValueError("name requerido")
        if int(capacity) <= 0:
            raise ValueError("capacity > 0")
        rid = "SMRUT-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_transport_routes"
                " (route_id, name, driver,"
                " capacity, assigned, active,"
                " created_at)"
                " VALUES (?, ?, ?, ?, 0, 1, ?)",
                (rid, str(name).strip(),
                 str(driver), int(capacity), now))
        return self.get_route(rid)

    def get_route(self, route_id
                  ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_transport_routes"
            " WHERE route_id = ?", (route_id,))
        if not row:
            return None
        return {"route_id":
                    str(row["route_id"]),
                "name": str(row["name"]),
                "driver": str(row["driver"]),
                "capacity": int(row["capacity"]),
                "assigned": int(row["assigned"]),
                "cupos": (int(row["capacity"])
                          - int(row["assigned"])),
                "active": bool(row["active"])}

    def add_stop(self, *, route_id, stop_name,
                 order_num=0) -> dict:
        if not str(stop_name).strip():
            raise ValueError(
                "stop_name requerido")
        sid = "SMSTP-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_transport_stops"
                " (stop_id, route_id, stop_name,"
                " order_num, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (sid, route_id,
                 str(stop_name).strip(),
                 int(order_num), now))
        return {"stop_id": sid,
                "route_id": route_id,
                "stop_name":
                    str(stop_name).strip()}

    def assign_student(self, *, route_id,
                       student_id,
                       stop_id="") -> dict:
        with self._db.transaction() as cursor:
            dup = cursor.execute(
                "SELECT assign_id FROM"
                " sm_transport_students WHERE"
                " student_id = ?",
                (student_id,)).fetchone()
            if dup is not None:
                raise ValueError(
                    "ya asignado a una ruta")
            row = cursor.execute(
                "SELECT capacity, assigned FROM"
                " sm_transport_routes WHERE"
                " route_id = ?",
                (route_id,)).fetchone()
            if row is None:
                raise KeyError(route_id)
            if (int(row["assigned"])
                    >= int(row["capacity"])):
                raise ValueError(
                    "ruta sin cupos")
            cursor.execute(
                "UPDATE sm_transport_routes SET"
                " assigned = assigned + 1 WHERE"
                " route_id = ?", (route_id,))
            aid = "SMASN-" + str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO"
                " sm_transport_students"
                " (assign_id, route_id,"
                " student_id, stop_id, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (aid, route_id, student_id,
                 str(stop_id),
                 self._clock.now()))
        return {"assign_id": aid,
                "route_id": route_id,
                "student_id": student_id}

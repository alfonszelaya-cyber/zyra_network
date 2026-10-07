
"""Role Dashboards Engine - cuadros por rol (S-2,
requisito del dueno) + capacidad exacta visible
y protegida (S-3).

ALUMNO: sus datos, notas (si hay motor conectado),
asistencia (si hay motor conectado) — degrada con
nota, nunca rompe.
PROFESOR: sus aulas (si la base registra
teacher_id) con cupos por aula.
DIRECTOR: SU escuela completa - aulas, grados,
secciones, turnos, capacidad, matriculados y CUPOS
EXACTOS por aula + plan de llenado.
MINISTERIO: escuelas por departamento y por
municipio, cuantas son, nombres, cuantas aulas,
cuantos grados, capacidad por turno y PLAN DE
LLENADO (aulas con cupo, ordenadas) — ES AHI donde
se llenan las matriculas automaticamente.

S-3 CAPACIDAD EXACTA ANTI-ERROR: guard_capacity()
lanza ValueError si un movimiento excede la
capacidad del aula. Ningun cuadro sugiere meter
alumnos de mas: solo cupos reales, aula por aula.

ROBUSTO POR DISENO: no asume APIs no verificadas.
Lee columnas reales via PRAGMA; motores opcionales
degradan con nota."""
from __future__ import annotations
from typing import Dict, List, Optional
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sm_school_geo", (
        "CREATE TABLE IF NOT EXISTS"
        " sm_school_geo (institution_id TEXT"
        " PRIMARY KEY, name TEXT NOT NULL DEFAULT"
        " '', department TEXT NOT NULL DEFAULT '',"
        " municipality TEXT NOT NULL DEFAULT '',"
        " updated_at REAL NOT NULL)",
    )),
)

class RoleDashboardsEngine:
    """Cuadros por rol + capacidad exacta (S-2/S-3)."""

    def __init__(self, db, clock,
                 student_registry,
                 classroom_engine,
                 enrollment_engine,
                 institution_registry=None,
                 evaluation_engine=None,
                 attendance_engine=None):
        self._db = db
        self._clock = clock
        self._students = student_registry
        self._cls = classroom_engine
        self._enr = enrollment_engine
        self._inst = institution_registry
        self._eval = evaluation_engine
        self._att = attendance_engine
        self._ccols = None
        MigrationRunner(db, "sm.roledash",
                        _MIGRATIONS).run(clock)

    # ---------- helpers internos ----------

    def _classroom_cols(self):
        if self._ccols is None:
            rows = self._db.query_all(
                "PRAGMA table_info(sm_classrooms)")
            self._ccols = set(
                str(r["name"]) for r in rows)
        return self._ccols

    def _geo_of(self, institution_id) -> dict:
        row = self._db.query_one(
            "SELECT name, department, municipality"
            " FROM sm_school_geo WHERE"
            " institution_id = ?",
            (str(institution_id),))
        if not row:
            return {}
        return {"name": str(row["name"]),
                "department":
                    str(row["department"]),
                "municipality":
                    str(row["municipality"])}

    def _aula_de_row(self, r) -> dict:
        keys = set(r.keys())
        cap = (int(r["capacity"])
               if "capacity" in keys else 0)
        enr = (int(r["enrolled"])
               if "enrolled" in keys else 0)
        g = (str(r["grade"])
             if "grade" in keys else "")
        t = (str(r["turn"])
             if "turn" in keys else "SIN_TURNO")
        return {"classroom_id":
                    str(r["classroom_id"]),
                "name": (str(r["name"])
                         if "name" in keys
                         else ""),
                "grade": g, "turn": t,
                "capacity": cap,
                "enrolled": enr,
                "cupos": cap - enr,
                "lleno": enr >= cap}

    # ---------- S-3: capacidad exacta ----------

    def capacity_state(self,
                       classroom_id) -> dict:
        r = self._db.query_one(
            "SELECT capacity, enrolled FROM"
            " sm_classrooms WHERE classroom_id"
            " = ?", (str(classroom_id),))
        if not r:
            raise KeyError(classroom_id)
        cap = int(r["capacity"] or 0)
        enr = int(r["enrolled"] or 0)
        return {"classroom_id":
                    str(classroom_id),
                "capacity": cap,
                "enrolled": enr,
                "cupos": cap - enr,
                "lleno": enr >= cap}

    def guard_capacity(self, classroom_id,
                       requesting=1) -> dict:
        """S-3: JAMAS se puede pedir cupo que
        no existe. Lanza ValueError si excede."""
        st = self.capacity_state(classroom_id)
        if (st["enrolled"] + int(requesting)
                > st["capacity"]):
            raise ValueError(
                "S-3 capacidad exacta: aula "
                + st["classroom_id"]
                + " capacidad "
                + str(st["capacity"])
                + ", matriculados "
                + str(st["enrolled"])
                + " — no caben "
                + str(requesting) + " mas"
                + " (cupos reales: "
                + str(st["cupos"]) + ")")
        return st

    # ---------- geografia escolar ----------

    def set_school_geo(self, *,
                       institution_id,
                       name="",
                       department="",
                       municipality="") -> dict:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "DELETE FROM sm_school_geo"
                " WHERE institution_id = ?",
                (str(institution_id),))
            cursor.execute(
                "INSERT INTO sm_school_geo"
                " (institution_id, name,"
                " department, municipality,"
                " updated_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (str(institution_id),
                 str(name), str(department),
                 str(municipality), now))
        return {"institution_id":
                    str(institution_id),
                "name": str(name),
                "department": str(department),
                "municipality":
                    str(municipality)}

    # ---------- ALUMNO ----------

    def student_dashboard(self,
                          student_id) -> dict:
        row = self._db.query_one(
            "SELECT * FROM sm_students WHERE"
            " student_id = ?",
            (str(student_id),))
        if not row:
            return {"role": "STUDENT",
                    "found": False}
        est = {k: row[k] for k in row.keys()}
        res = {"role": "STUDENT",
               "found": True,
               "student": est,
               "average": None,
               "attendance_pct": None}
        if self._eval is not None:
            try:
                avg = self._eval.average_of(
                    student_id)
                res["average"] = avg.get(
                    "average")
            except Exception:
                pass
        if self._att is not None:
            try:
                att = self._att.rate(
                    student_id)
                res["attendance_pct"] = \
                    att.get("present_rate_pct")
            except Exception:
                pass
        return res

    # ---------- PROFESOR ----------

    def teacher_dashboard(self, *,
                          teacher_id,
                          institution_id=""
                          ) -> dict:
        grupos = []
        cols = self._classroom_cols()
        if "teacher_id" in cols:
            rows = self._db.query_all(
                "SELECT * FROM sm_classrooms"
                " WHERE teacher_id = ?"
                " ORDER BY grade, section,"
                " turn", (str(teacher_id),))
            for r in rows:
                if institution_id and \
                        str(r["institution_id"]
                            ) != institution_id:
                    continue
                grupos.append(
                    self._aula_de_row(r))
        return {"role": "TEACHER",
                "teacher_id": str(teacher_id),
                "aulas": len(grupos),
                "grupos": grupos,
                "note": "" if grupos else
                "sin aulas asignadas (esta"
                " base no registra teacher_id"
                " o el profesor no tiene)"}

    # ---------- DIRECTOR ----------

    def director_dashboard(self, *,
                           institution_id,
                           school_year="2026"
                           ) -> dict:
        """SU escuela completa con cupos EXACTOS
        por aula. Los totales salen de las aulas
        reales."""
        rows = self._db.query_all(
            "SELECT * FROM sm_classrooms WHERE"
            " institution_id = ? AND"
            " school_year = ? ORDER BY grade,"
            " section, turn",
            (str(institution_id),
             str(school_year)))
        aulas = []
        tot_cap = 0
        tot_enr = 0
        grados = set()
        turnos = set()
        for r in rows:
            a = self._aula_de_row(r)
            aulas.append(a)
            tot_cap += a["capacity"]
            tot_enr += a["enrolled"]
            if a["grade"]:
                grados.add(a["grade"])
            turnos.add(a["turn"])
        return {"role": "DIRECTOR",
                "institution_id":
                    str(institution_id),
                "school_year": str(school_year),
                "aulas": len(aulas),
                "grados": sorted(grados),
                "turnos": sorted(turnos),
                "total_capacity": tot_cap,
                "total_enrolled": tot_enr,
                "total_cupos":
                    tot_cap - tot_enr,
                "classroom_rows": aulas,
                "plan_de_llenado":
                    [a for a in aulas
                     if a["cupos"] > 0]}

    # ---------- MINISTERIO ----------

    def ministry_dashboard(self, *,
                           department="",
                           municipality=""
                           ) -> dict:
        """Escuelas por departamento/municipio,
        capacidad, turnos y plan de llenado
        (donde se llenan las matriculas)."""
        rows = self._db.query_all(
            "SELECT DISTINCT institution_id"
            " FROM sm_classrooms")
        ids = sorted(set(
            str(r["institution_id"])
            for r in rows))
        escuelas = []
        plan = []
        t_esc = t_aulas = t_cap = t_enr = 0
        for iid in ids:
            geo = self._geo_of(iid)
            if department or municipality:
                if not geo:
                    continue
                if department and geo.get(
                        "department"
                        ) != department:
                    continue
                if municipality and geo.get(
                        "municipality"
                        ) != municipality:
                    continue
            filas = self._db.query_all(
                "SELECT * FROM sm_classrooms"
                " WHERE institution_id = ?",
                (iid,))
            aulas = len(filas)
            cap = enr = 0
            grados = set()
            por_turno = {}
            for r in filas:
                a = self._aula_de_row(r)
                cap += a["capacity"]
                enr += a["enrolled"]
                if a["grade"]:
                    grados.add(a["grade"])
                pt = por_turno.setdefault(
                    a["turn"],
                    {"capacidad": 0,
                     "matriculados": 0})
                pt["capacidad"] += \
                    a["capacity"]
                pt["matriculados"] += \
                    a["enrolled"]
                if a["cupos"] > 0:
                    plan.append({
                        "institution_id": iid,
                        "classroom_id":
                            a["classroom_id"],
                        "grade": a["grade"],
                        "turn": a["turn"],
                        "cupos": a["cupos"]})
            escuelas.append({
                "institution_id": iid,
                "nombre":
                    geo.get("name", ""),
                "department": geo.get(
                    "department",
                    "SIN_GEO"),
                "municipality": geo.get(
                    "municipality",
                    "SIN_GEO"),
                "aulas": aulas,
                "grados": sorted(grados),
                "turnos": sorted(por_turno),
                "capacidad_total": cap,
                "matriculados": enr,
                "cupos": cap - enr,
                "capacidad_por_turno":
                    por_turno})
            t_esc += 1
            t_aulas += aulas
            t_cap += cap
            t_enr += enr
        return {"role": "MINISTRY",
                "filtro": {
                    "department":
                        str(department),
                    "municipality":
                        str(municipality)},
                "escuelas": escuelas,
                "total_escuelas": t_esc,
                "total_aulas": t_aulas,
                "total_capacidad": t_cap,
                "total_matriculados": t_enr,
                "total_cupos":
                    t_cap - t_enr,
                "plan_de_llenado": sorted(
                    plan,
                    key=lambda x: -x["cupos"])}

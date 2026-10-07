
"""Auto Assignment Engine (S-7) - asignacion
automatica de matricula.

Flujo del dueno: encuentra escuela -> comprueba
grado/jornada/CUPO REAL -> selecciona seccion/
aula -> confirma matricula (enroll: el cupo se
reclama UNA SOLA VEZ).

- Si el alumno tiene institucion en su expediente
  canonico, SOLO busca ahi (la escuela del
  expediente manda).
- Si no, DESCUBRE escuelas con secciones de ese
  nivel/grado y cupo disponible (via
  available_sections, que solo devuelve secciones
  CON cupo — verificado en fix2).
- Respeta la preferencia de turno en orden;
  JAMAS asigna un turno fuera del orden pedido.
- NO_CUPOS honesto (regla 66): nota con lo
  intentado y turnos con cupo por escuela.
- preview(): muestra el plan SIN enrollar.

Solo APIs verificadas en verde: available_sections,
enroll, get (StudentRegistryEngine)."""
from __future__ import annotations
from typing import Dict, List, Optional
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)

_TURNS = ("MATUTINA", "VESPERTINA",
          "NOCTURNA")


class AutoAssignmentEngine:
    """Asignacion automatica (S-7)."""

    def __init__(self, db, clock,
                 student_registry,
                 classroom_engine,
                 enrollment_engine):
        self._db = db
        self._clock = clock
        self._students = student_registry
        self._cls = classroom_engine
        self._enr = enrollment_engine

    def _instituciones(self, *, student_id,
                       institution_id,
                       school_year, level,
                       grade) -> List[str]:
        if str(institution_id).strip():
            return [str(institution_id)]
        est = self._students.get(
            str(student_id))
        home = str((est or {}).get(
            "institution_id") or "")
        if home:
            return [home]
        rows = self._db.query_all(
            "SELECT DISTINCT institution_id"
            " FROM sm_classrooms WHERE"
            " school_year = ? AND level = ?"
            " AND grade = ?",
            (str(school_year),
             str(level), str(grade)))
        return sorted(set(
            str(r["institution_id"])
            for r in rows))

    def _opciones(self, iid, *, school_year,
                  level, grade) -> List[dict]:
        try:
            return list(
                self._cls.available_sections(
                    institution_id=iid,
                    school_year=str(school_year),
                    level=str(level),
                    grade=str(grade)))
        except Exception:
            return []

    def preview(self, *, student_id, level,
                grade, turn_order=None,
                institution_id="",
                school_year="2026") -> dict:
        """Plan sin enrollar (lectura)."""
        orden = [t for t in (
            turn_order or list(_TURNS))]
        iids = self._instituciones(
            student_id=student_id,
            institution_id=institution_id,
            school_year=school_year,
            level=level, grade=grade)
        plan = []
        for iid in iids:
            ops = self._opciones(
                iid, school_year=school_year,
                level=level, grade=grade)
            plan.append({
                "institution_id": iid,
                "turnos_con_cupo": sorted(
                    set(str(o["turn"])
                        for o in ops)),
                "secciones": [
                    {"classroom_id":
                         str(o["classroom_id"]),
                     "turn": str(o["turn"])}
                    for o in ops]})
        return {"student_id":
                    str(student_id),
                "level": str(level),
                "grade": str(grade),
                "turn_order": orden,
                "plan": plan}

    def assign(self, *, student_id, level,
               grade, turn_order=None,
               institution_id="",
               school_year="2026") -> dict:
        """Asigna: escuela -> turno pedido ->
        seccion con cupo -> enroll (cupo UNA
        vez). NO_CUPOS honesto si nada aplica."""
        orden = [str(t).upper() for t in (
            turn_order or list(_TURNS))]
        iids = self._instituciones(
            student_id=student_id,
            institution_id=institution_id,
            school_year=school_year,
            level=level, grade=grade)
        tried = []
        for iid in iids:
            ops = self._opciones(
                iid, school_year=school_year,
                level=level, grade=grade)
            for turno in orden:
                for op in ops:
                    if str(op["turn"]) \
                            != turno:
                        continue
                    enr = self._enr.enroll(
                        student_id=str(
                            student_id),
                        classroom_id=str(
                            op["classroom_id"]),
                        school_year=str(
                            school_year))
                    return {
                        "status": "ASIGNADO",
                        "student_id": str(
                            student_id),
                        "institution_id": iid,
                        "classroom_id": str(
                            op["classroom_id"]),
                        "turn": turno,
                        "enrollment": enr}
            tried.append({
                "institution_id": iid,
                "turnos_con_cupo": sorted(
                    set(str(o["turn"])
                        for o in ops)),
                "turnos_pedidos": orden})
        return {
            "status": "NO_CUPOS",
            "student_id": str(student_id),
            "level": str(level),
            "grade": str(grade),
            "turn_order": orden,
            "tried": tried,
            "note": ("sin seccion con cupo"
                     " para " + str(level)
                     + " " + str(grade)
                     + " en turnos "
                     + ", ".join(orden)
                     + " (escuelas"
                       " intentadas: "
                     + str(len(tried))
                     + ")")}

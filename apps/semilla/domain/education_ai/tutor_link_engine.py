
"""Tutor Link Engine (S-8) - la IA tutora como
PARTE del ciclo escolar, no un chatbot suelto.

Conecta: expediente canonico (StudentRegistry)
+ notas (sm_evaluations, flujo S-9) + asistencia
por clase (sm_class_attendance, flujo S-6) +
sesiones de tutoria (sm_tutor_sessions, DDL
confirmado) -> OBJETIVO concreto de estudio con
dificultad derivada del promedio real.

FOCO UNICO (v2): el alumno tiene UN solo objetivo
ACTIVO a la vez — al fijar uno nuevo, los
anteriores de CUALQUIER materia quedan
REEMPLAZADO (el GENERAL de arranque cede ante
el primero con notas reales).

snapshot(): estado consolidado del alumno.
next_objective(): elige la materia con PEOR
promedio (razon honesta, regla 66) y fija
dificultad 1..4 (sin notas -> GENERAL nivel 1).
record_attempt(): acierto sube nivel y racha
(racha 3 -> objetivo COMPLETADO); error baja
nivel (min 1) y resetea racha; sincroniza la
sesion de tutoria abierta de esa materia.

Regla 76: ORDER BY rowid (nunca timestamps con
reloj congelado). Regla 61: promedios Decimal
2d. Regla 68: solo carpetas existentes."""
from __future__ import annotations
import uuid
from decimal import Decimal
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "ai_canonical_guarantees", (
        "CREATE TABLE IF NOT EXISTS"
        " sm_evaluations (evaluation_id TEXT"
        " PRIMARY KEY, student_id TEXT NOT NULL,"
        " subject TEXT NOT NULL, period TEXT NOT"
        " NULL, score TEXT NOT NULL, scale_max"
        " TEXT NOT NULL DEFAULT '10.00',"
        " eval_type TEXT NOT NULL DEFAULT"
        " 'EXAMEN', teacher_id TEXT NOT NULL"
        " DEFAULT '', detail TEXT NOT NULL"
        " DEFAULT '', created_at REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS"
        " sm_class_attendance (class_att_id TEXT"
        " PRIMARY KEY, student_id TEXT NOT NULL,"
        " classroom_id TEXT NOT NULL, subject TEXT"
        " NOT NULL, date TEXT NOT NULL, time_slot"
        " TEXT NOT NULL DEFAULT '', status TEXT"
        " NOT NULL, teacher_id TEXT NOT NULL"
        " DEFAULT '', detail TEXT NOT NULL DEFAULT"
        " '', created_at REAL NOT NULL,"
        " UNIQUE(student_id, classroom_id, subject,"
        " date, time_slot))",
        "CREATE TABLE IF NOT EXISTS"
        " sm_tutor_sessions (session_id TEXT"
        " PRIMARY KEY, student_id TEXT NOT NULL,"
        " subject TEXT NOT NULL, level INTEGER NOT"
        " NULL DEFAULT 1, streak INTEGER NOT NULL"
        " DEFAULT 0, mode TEXT NOT NULL DEFAULT"
        " 'TUTOR', status TEXT NOT NULL DEFAULT"
        " 'OPEN', created_at REAL NOT NULL,"
        " updated_at REAL NOT NULL)",
    )),
    Migration(2, "ai_own_tables", (
        "CREATE TABLE IF NOT EXISTS"
        " sm_ai_objectives (objective_id TEXT"
        " PRIMARY KEY, student_id TEXT NOT NULL,"
        " subject TEXT NOT NULL, difficulty INTEGER"
        " NOT NULL DEFAULT 1, reason TEXT NOT NULL"
        " DEFAULT '', status TEXT NOT NULL DEFAULT"
        " 'ACTIVO', created_at REAL NOT NULL,"
        " updated_at REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS"
        " sm_ai_attempts (attempt_id TEXT PRIMARY"
        " KEY, objective_id TEXT NOT NULL,"
        " student_id TEXT NOT NULL, correct INTEGER"
        " NOT NULL, detail TEXT NOT NULL DEFAULT"
        " '', created_at REAL NOT NULL)",
    )),
)


def _difficulty_from_average(avg):
    if avg is None:
        return 1
    d = Decimal(str(avg))
    if d < Decimal("5.00"):
        return 1
    if d < Decimal("7.00"):
        return 2
    if d < Decimal("9.00"):
        return 3
    return 4


class TutorLinkEngine:
    """IA tutora integrada al ciclo (S-8)."""

    def __init__(self, db, clock,
                 student_registry):
        self._db = db
        self._clock = clock
        self._students = student_registry
        MigrationRunner(db, "sm.ailink",
                        _MIGRATIONS).run(clock)

    def _averages_by_subject(self,
                             student_id) -> dict:
        rows = self._db.query_all(
            "SELECT subject, score FROM"
            " sm_evaluations WHERE student_id ="
            " ?", (str(student_id),))
        acc = {}
        for r in rows:
            try:
                acc.setdefault(
                    str(r["subject"]),
                    []).append(
                    Decimal(str(r["score"])))
            except Exception:
                continue
        out = {}
        for subj, vals in acc.items():
            out[subj] = str(
                (sum(vals)
                 / Decimal(len(vals)))
                .quantize(Decimal("0.01")))
        return out

    def snapshot(self, student_id) -> dict:
        est = self._students.get(
            str(student_id))
        if est is None:
            return {"found": False}
        avgs = self._averages_by_subject(
            student_id)
        att_rows = self._db.query_all(
            "SELECT status, COUNT(*) AS n FROM"
            " sm_class_attendance WHERE"
            " student_id = ? GROUP BY status",
            (str(student_id),))
        attendance = {
            str(r["status"]): int(r["n"])
            for r in att_rows}
        sess = self._db.query_all(
            "SELECT session_id, subject, level,"
            " streak, status FROM"
            " sm_tutor_sessions WHERE"
            " student_id = ? ORDER BY rowid",
            (str(student_id),))
        sessions = [
            {"session_id":
                 str(r["session_id"]),
             "subject": str(r["subject"]),
             "level": int(r["level"]),
             "streak": int(r["streak"]),
             "status": str(r["status"])}
            for r in sess]
        objs = self._db.query_all(
            "SELECT objective_id, subject,"
            " difficulty, reason, status FROM"
            " sm_ai_objectives WHERE student_id"
            " = ? AND status = 'ACTIVO'"
            " ORDER BY rowid",
            (str(student_id),))
        actives = [
            {"objective_id":
                 str(r["objective_id"]),
             "subject": str(r["subject"]),
             "difficulty": int(r["difficulty"]),
             "reason": str(r["reason"])}
            for r in objs]
        return {"found": True,
                "student": est,
                "averages": avgs,
                "attendance": attendance,
                "tutor_sessions": sessions,
                "active_objectives": actives}

    def next_objective(self, student_id,
                       subject=None) -> dict:
        avgs = self._averages_by_subject(
            student_id)
        if str(subject or "").strip():
            chosen = str(subject)
            avg = avgs.get(chosen)
            if avg is None:
                reason = ("sin notas de "
                          + chosen
                          + ": nivel inicial")
                diff = 1
            else:
                diff = _difficulty_from_average(
                    avg)
                reason = ("promedio " + avg
                          + " en " + chosen)
        elif avgs:
            chosen = sorted(
                avgs.items(),
                key=lambda kv:
                    (Decimal(kv[1]),
                     kv[0]))[0][0]
            avg = avgs[chosen]
            diff = _difficulty_from_average(avg)
            reason = ("peor promedio " + avg
                      + " en " + chosen)
        else:
            chosen = "GENERAL"
            diff = 1
            reason = ("sin notas: nivel"
                      " inicial GENERAL")
        with self._db.transaction() as cur:
            cur.execute(
                "UPDATE sm_ai_objectives SET"
                " status = 'REEMPLAZADO',"
                " updated_at = ? WHERE"
                " student_id = ? AND status ="
                " 'ACTIVO'",
                (self._clock.now(),
                 str(student_id)))
            oid = ("SMOBJ-"
                   + uuid.uuid4().hex[:10])
            cur.execute(
                "INSERT INTO sm_ai_objectives"
                " (objective_id, student_id,"
                " subject, difficulty, reason,"
                " status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?,"
                " 'ACTIVO', ?, ?)",
                (oid, str(student_id), chosen,
                 int(diff), reason,
                 self._clock.now(),
                 self._clock.now()))
        return {"objective_id": oid,
                "student_id": str(student_id),
                "subject": chosen,
                "difficulty": int(diff),
                "reason": reason,
                "status": "ACTIVO"}

    def record_attempt(self, objective_id, *,
                       correct, detail="") -> dict:
        row = self._db.query_one(
            "SELECT * FROM sm_ai_objectives"
            " WHERE objective_id = ?",
            (str(objective_id),))
        if not row:
            raise KeyError(objective_id)
        oid = str(row["objective_id"])
        sid = str(row["student_id"])
        subj = str(row["subject"])
        diff = int(row["difficulty"])
        rows = self._db.query_all(
            "SELECT correct FROM sm_ai_attempts"
            " WHERE objective_id = ?"
            " ORDER BY rowid DESC LIMIT 3",
            (oid,))
        streak = 0
        for r in rows:
            if int(r["correct"]) == 1:
                streak += 1
            else:
                break
        if bool(correct):
            new_diff = min(5, diff + 1)
            new_streak = streak + 1
        else:
            new_diff = max(1, diff - 1)
            new_streak = 0
        aid = ("SMAAT-"
               + uuid.uuid4().hex[:10])
        with self._db.transaction() as cur:
            cur.execute(
                "INSERT INTO sm_ai_attempts"
                " (attempt_id, objective_id,"
                " student_id, correct, detail,"
                " created_at) VALUES"
                " (?, ?, ?, ?, ?, ?)",
                (aid, oid, sid,
                 1 if bool(correct) else 0,
                 str(detail),
                 self._clock.now()))
            status = "ACTIVO"
            if new_streak >= 3:
                status = "COMPLETADO"
                cur.execute(
                    "UPDATE sm_ai_objectives"
                    " SET status = 'COMPLETADO',"
                    " updated_at = ? WHERE"
                    " objective_id = ?",
                    (self._clock.now(), oid))
            else:
                cur.execute(
                    "UPDATE sm_ai_objectives SET"
                    " difficulty = ?, updated_at"
                    " = ? WHERE objective_id = ?",
                    (new_diff,
                     self._clock.now(), oid))
            srow = cur.execute(
                "SELECT session_id FROM"
                " sm_tutor_sessions WHERE"
                " student_id = ? AND subject = ?"
                " AND status = 'OPEN'"
                " ORDER BY rowid LIMIT 1",
                (sid, subj)).fetchone()
            if srow is not None:
                cur.execute(
                    "UPDATE sm_tutor_sessions"
                    " SET level = ?, streak = ?,"
                    " updated_at = ? WHERE"
                    " session_id = ?",
                    (new_diff, new_streak,
                     self._clock.now(),
                     str(srow[0])))
            else:
                cur.execute(
                    "INSERT INTO"
                    " sm_tutor_sessions"
                    " (session_id, student_id,"
                    " subject, level, streak,"
                    " mode, status, created_at,"
                    " updated_at) VALUES"
                    " (?, ?, ?, ?, ?, 'TUTOR',"
                    " 'OPEN', ?, ?)",
                    ("SMSES-"
                     + uuid.uuid4().hex[:10],
                     sid, subj, new_diff,
                     new_streak,
                     self._clock.now(),
                     self._clock.now()))
        return {"attempt_id": aid,
                "objective_id": oid,
                "difficulty": new_diff,
                "streak": new_streak,
                "objective_status": status}

    def objectives_of(self, student_id) -> list:
        rows = self._db.query_all(
            "SELECT objective_id, subject,"
            " difficulty, reason, status FROM"
            " sm_ai_objectives WHERE student_id"
            " = ? ORDER BY rowid",
            (str(student_id),))
        return [
            {"objective_id":
                 str(r["objective_id"]),
             "subject": str(r["subject"]),
             "difficulty": int(r["difficulty"]),
             "reason": str(r["reason"]),
             "status": str(r["status"])}
            for r in rows]

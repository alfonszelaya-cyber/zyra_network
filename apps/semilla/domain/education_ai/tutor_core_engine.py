
"""Tutor Core Engine - EL CORAZON de SEMILLA (SM2).
Pistas graduales que explican el metodo sin
entregar la respuesta. Modo EXAMEN bloquea ayuda.
Dificultad dinamica persistente."""
from __future__ import annotations
from typing import Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sm_tutor_sessions", (
        "CREATE TABLE IF NOT EXISTS sm_tutor_sessions (session_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, subject TEXT NOT NULL, level INTEGER NOT NULL DEFAULT 1, streak INTEGER NOT NULL DEFAULT 0, mode TEXT NOT NULL DEFAULT 'TUTOR', status TEXT NOT NULL DEFAULT 'OPEN', created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
    Migration(2, "sm_tutor_attempts", (
        "CREATE TABLE IF NOT EXISTS sm_tutor_attempts (attempt_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, challenge TEXT NOT NULL, student_answer TEXT NOT NULL DEFAULT '', correct INTEGER NOT NULL, hints_used INTEGER NOT NULL DEFAULT 0, points INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL)",
    )),
)

class TutorCoreEngine:
    """Sesiones del tutor IA (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.tutor",
                        _MIGRATIONS).run(clock)

    def start_session(self, *, student_id,
                      subject, mode="TUTOR") -> dict:
        if mode not in ("TUTOR", "EXAM"):
            mode = "TUTOR"
        sid = "SMTUT-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_tutor_sessions"
                " (session_id, student_id,"
                " subject, level, streak, mode,"
                " status, created_at, updated_at)"
                " VALUES (?, ?, ?, 1, 0, ?,"
                " 'OPEN', ?, ?)",
                (sid, student_id,
                 str(subject).strip(), mode,
                 now, now))
        return self.get_session(sid)

    def get_session(self, session_id
                    ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_tutor_sessions"
            " WHERE session_id = ?",
            (session_id,))
        if not row:
            return None
        return {"session_id":
                    str(row["session_id"]),
                "student_id":
                    str(row["student_id"]),
                "subject": str(row["subject"]),
                "level": int(row["level"]),
                "streak": int(row["streak"]),
                "mode": str(row["mode"]),
                "status": str(row["status"])}

    def hint(self, *, mode, hints_used,
             solution_hint) -> dict:
        if mode == "EXAM":
            return {"allowed": False,
                    "reason": "modo examen:"
                              " ayuda bloqueada"}
        if hints_used >= 3:
            return {"allowed": False,
                    "reason": "maximo 3 pistas:"
                              " pide ayuda al"
                              " maestro"}
        niveles = ["pista conceptual: "
                   + str(solution_hint),
                   "pista de metodo: revisa el"
                   " paso anterior y como"
                   " aplicaste la operacion",
                   "pista de verificacion:"
                   " comprueba tu resultado"
                   " sustituyendo"]
        return {"allowed": True,
                "hint": niveles[int(hints_used)],
                "integrity": "el tutor explica el"
                             " metodo, no entrega"
                             " la respuesta"}

    def record_attempt(self, *, session_id,
                       challenge,
                       student_answer, correct,
                       hints_used=0) -> dict:
        s = self.get_session(session_id)
        if not s:
            raise KeyError(session_id)
        if s["status"] != "OPEN":
            raise ValueError("sesion cerrada")
        aid = "SMATT-" + str(uuid.uuid4())
        now = self._clock.now()
        pts = 0
        if correct:
            pts = 10 - (min(int(hints_used), 3)
                        * 2)
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_tutor_attempts"
                " (attempt_id, session_id,"
                " challenge, student_answer,"
                " correct, hints_used, points,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (aid, session_id,
                 str(challenge),
                 str(student_answer),
                 1 if correct else 0,
                 int(hints_used), pts, now))
            if correct:
                cursor.execute(
                    "UPDATE sm_tutor_sessions"
                    " SET level = level + 1,"
                    " streak = streak + 1,"
                    " updated_at = ? WHERE"
                    " session_id = ?",
                    (now, session_id))
            else:
                cursor.execute(
                    "UPDATE sm_tutor_sessions"
                    " SET level = CASE WHEN"
                    " level > 1 THEN level - 1"
                    " ELSE 1 END, streak = 0,"
                    " updated_at = ? WHERE"
                    " session_id = ?",
                    (now, session_id))
        return {"attempt_id": aid,
                "correct": bool(correct),
                "points": pts}

    def session_points(self, session_id) -> int:
        row = self._db.query_one(
            "SELECT COALESCE(SUM(points),0) AS p"
            " FROM sm_tutor_attempts WHERE"
            " session_id = ?", (session_id,))
        return int(row["p"]) if row else 0

    def close_session(self, session_id) -> dict:
        self._db.execute(
            "UPDATE sm_tutor_sessions SET"
            " status = 'CLOSED', updated_at = ?"
            " WHERE session_id = ?",
            (self._clock.now(), session_id))
        return self.get_session(session_id)

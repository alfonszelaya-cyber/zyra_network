
"""Registro canonico de migraciones (S-12) - UN
bootstrap idempotente con las tablas de DDL
100% CONOCIDO (esquema exacto del repo).

EXCLUIDAS A PROPOSITO: sm_students,
sm_classrooms, sm_enrollments, sm_history,
sm_institutions y demas nucleo — sus DDL
completos no han sido auditados; sus engines
duenos los crean. Un registro que creara esas
tablas con esquema supuesto corromperia el
nucleo en una db fresca (regla 66/68/69)."""
from __future__ import annotations
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "canonical_known_ddl", (
        "CREATE TABLE IF NOT EXISTS"
        " sm_home_registrations (request_id TEXT"
        " PRIMARY KEY, responsable_zid TEXT NOT"
        " NULL, responsable_name TEXT NOT NULL,"
        " relation TEXT NOT NULL, student_id TEXT,"
        " child_name TEXT NOT NULL, birth_date"
        " TEXT NOT NULL DEFAULT '', child_zid TEXT"
        " NOT NULL DEFAULT '', child_zid_status"
        " TEXT NOT NULL DEFAULT 'NONE',"
        " institution_id TEXT NOT NULL, level TEXT"
        " NOT NULL, grade TEXT NOT NULL, turn TEXT"
        " NOT NULL DEFAULT 'MATUTINA',"
        " classroom_id TEXT NOT NULL DEFAULT '',"
        " pickup_json TEXT NOT NULL DEFAULT '[]',"
        " emergency_json TEXT NOT NULL DEFAULT"
        " '[]', status TEXT NOT NULL DEFAULT"
        " 'PENDING_DOCS', note TEXT NOT NULL"
        " DEFAULT '', created_at REAL NOT NULL,"
        " updated_at REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS"
        " sm_school_geo (institution_id TEXT"
        " PRIMARY KEY, name TEXT NOT NULL DEFAULT"
        " '', department TEXT NOT NULL DEFAULT '',"
        " municipality TEXT NOT NULL DEFAULT '',"
        " updated_at REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS"
        " sm_evaluations (evaluation_id TEXT"
        " PRIMARY KEY, student_id TEXT NOT NULL,"
        " subject TEXT NOT NULL, period TEXT NOT"
        " NULL, score TEXT NOT NULL, scale_max"
        " TEXT NOT NULL DEFAULT '10.00',"
        " eval_type TEXT NOT NULL DEFAULT"
        " 'EXAMEN', teacher_id TEXT NOT NULL"
        " DEFAULT '', detail TEXT NOT NULL DEFAULT"
        " '', created_at REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS"
        " sm_family_comms (comm_id TEXT PRIMARY"
        " KEY, student_id TEXT NOT NULL,"
        " from_role TEXT NOT NULL, subject TEXT"
        " NOT NULL, body TEXT NOT NULL DEFAULT '',"
        " created_at REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS"
        " sm_calendar (event_id TEXT PRIMARY KEY,"
        " date TEXT NOT NULL, event_type TEXT NOT"
        " NULL, title TEXT NOT NULL, subject TEXT"
        " NOT NULL DEFAULT '', created_at REAL NOT"
        " NULL)",
        "CREATE TABLE IF NOT EXISTS"
        " sm_tutor_sessions (session_id TEXT"
        " PRIMARY KEY, student_id TEXT NOT NULL,"
        " subject TEXT NOT NULL, level INTEGER NOT"
        " NULL DEFAULT 1, streak INTEGER NOT NULL"
        " DEFAULT 0, mode TEXT NOT NULL DEFAULT"
        " 'TUTOR', status TEXT NOT NULL DEFAULT"
        " 'OPEN', created_at REAL NOT NULL,"
        " updated_at REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS"
        " sm_tutor_attempts (attempt_id TEXT"
        " PRIMARY KEY, session_id TEXT NOT NULL,"
        " challenge TEXT NOT NULL, student_answer"
        " TEXT NOT NULL DEFAULT '', correct"
        " INTEGER NOT NULL, hints_used INTEGER NOT"
        " NULL DEFAULT 0, points INTEGER NOT NULL"
        " DEFAULT 0, created_at REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS"
        " sm_cycle_years (year_id TEXT PRIMARY"
        " KEY, institution_id TEXT NOT NULL,"
        " school_year TEXT NOT NULL, start_date"
        " TEXT NOT NULL DEFAULT '', end_date TEXT"
        " NOT NULL DEFAULT '', status TEXT NOT"
        " NULL DEFAULT 'ACTIVO', created_at REAL"
        " NOT NULL, UNIQUE(institution_id,"
        " school_year))",
        "CREATE TABLE IF NOT EXISTS"
        " sm_cycle_events (event_id TEXT PRIMARY"
        " KEY, student_id TEXT NOT NULL,"
        " event_type TEXT NOT NULL, school_year"
        " TEXT NOT NULL DEFAULT '', detail TEXT"
        " NOT NULL DEFAULT '', created_at REAL"
        " NOT NULL)",
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
        "CREATE TABLE IF NOT EXISTS"
        " sm_learning_paths (path_id TEXT PRIMARY"
        " KEY, student_id TEXT NOT NULL, subject"
        " TEXT NOT NULL, step_no INTEGER NOT NULL,"
        " difficulty INTEGER NOT NULL DEFAULT 1,"
        " status TEXT NOT NULL DEFAULT 'ACTIVO',"
        " created_at REAL NOT NULL, updated_at"
        " REAL NOT NULL, UNIQUE(student_id,"
        " subject, step_no))",
        "CREATE TABLE IF NOT EXISTS"
        " sm_certificates (cert_id TEXT PRIMARY"
        " KEY, cert_code TEXT NOT NULL UNIQUE,"
        " student_id TEXT NOT NULL, cert_type TEXT"
        " NOT NULL, detail TEXT NOT NULL DEFAULT"
        " '', issued_by TEXT NOT NULL DEFAULT '',"
        " status TEXT NOT NULL DEFAULT 'VIGENTE',"
        " revoked_reason TEXT NOT NULL DEFAULT"
        " '', prev_hash TEXT NOT NULL DEFAULT '',"
        " entry_hash TEXT NOT NULL, created_at"
        " REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS"
        " sm_admission_apps (app_id TEXT PRIMARY"
        " KEY, student_id TEXT NOT NULL DEFAULT"
        " '', applicant_name TEXT NOT NULL,"
        " relation TEXT NOT NULL DEFAULT '',"
        " target_institution TEXT NOT NULL,"
        " target_level TEXT NOT NULL, target_grade"
        " TEXT NOT NULL, status TEXT NOT NULL"
        " DEFAULT 'PENDIENTE', note TEXT NOT NULL"
        " DEFAULT '', created_at REAL NOT NULL,"
        " updated_at REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS"
        " sm_teacher_assignments (assignment_id"
        " TEXT PRIMARY KEY, teacher_id TEXT NOT"
        " NULL, classroom_id TEXT NOT NULL,"
        " subject TEXT NOT NULL DEFAULT '', day"
        " TEXT NOT NULL DEFAULT '', time_slot"
        " TEXT NOT NULL DEFAULT '', created_at"
        " REAL NOT NULL, UNIQUE(classroom_id,"
        " day, time_slot))",
    )),
)

KNOWN_TABLES = (
    "sm_home_registrations", "sm_school_geo",
    "sm_evaluations", "sm_family_comms",
    "sm_calendar", "sm_tutor_sessions",
    "sm_tutor_attempts", "sm_cycle_years",
    "sm_cycle_events", "sm_class_attendance",
    "sm_ai_objectives", "sm_ai_attempts",
    "sm_learning_paths", "sm_certificates",
    "sm_admission_apps", "sm_teacher_assignments")


def run_all(db, clock) -> None:
    """Bootstrap idempotente de tablas conocidas."""
    MigrationRunner(
        db, "sm.canonical",
        _MIGRATIONS).run(clock)

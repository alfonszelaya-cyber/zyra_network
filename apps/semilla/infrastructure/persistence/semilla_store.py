"""SEMILLA durable store (v2: + tutor tables)."""
from __future__ import annotations

import uuid

from shared_engines.storage.database import Database
from shared_engines.storage.migrations import Migration, MigrationRunner

ROLES = ("alumno", "profesor", "institucion")
GRADE_LEVELS = ("prekinder", "kinder", "primaria", "secundaria", "universidad")

_MIGRATIONS = (
    Migration(
        1,
        "semilla",
        (
            "CREATE TABLE semilla_accounts ("
            " account_id TEXT PRIMARY KEY,"
            " zid TEXT,"
            " name TEXT NOT NULL,"
            " role TEXT NOT NULL,"
            " school TEXT,"
            " grade TEXT,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE semilla_grades ("
            " grade_id TEXT PRIMARY KEY,"
            " student_account TEXT NOT NULL,"
            " subject TEXT NOT NULL,"
            " score REAL NOT NULL,"
            " teacher_account TEXT NOT NULL,"
            " recorded_at REAL NOT NULL)",
            "CREATE TABLE semilla_attendance ("
            " att_id TEXT PRIMARY KEY,"
            " student_account TEXT NOT NULL,"
            " present INTEGER NOT NULL,"
            " recorded_at REAL NOT NULL)",
            "CREATE TABLE semilla_welfare ("
            " welfare_id TEXT PRIMARY KEY,"
            " student_account TEXT NOT NULL,"
            " mood TEXT NOT NULL,"
            " alert INTEGER NOT NULL DEFAULT 0,"
            " recorded_at REAL NOT NULL)",
            "CREATE TABLE semilla_scholarships ("
            " scholarship_id TEXT PRIMARY KEY,"
            " student_account TEXT NOT NULL,"
            " reason TEXT NOT NULL,"
            " granted_at REAL NOT NULL)",
        ),
    ),
    Migration(
        2,
        "semilla_tutor",
        (
            "CREATE TABLE semilla_challenge_state ("
            " student_account TEXT PRIMARY KEY,"
            " domain TEXT NOT NULL,"
            " difficulty INTEGER NOT NULL,"
            " updated_at REAL NOT NULL)",
            "CREATE TABLE semilla_attempts ("
            " attempt_id TEXT PRIMARY KEY,"
            " student_account TEXT NOT NULL,"
            " domain TEXT NOT NULL,"
            " difficulty INTEGER NOT NULL,"
            " correct INTEGER NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE semilla_talents ("
            " talent_id TEXT PRIMARY KEY,"
            " student_account TEXT NOT NULL,"
            " domain TEXT NOT NULL,"
            " evidence TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE semilla_rewards ("
            " reward_id TEXT PRIMARY KEY,"
            " student_account TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " detail TEXT,"
            " points INTEGER NOT NULL DEFAULT 0,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE semilla_messages ("
            " message_id TEXT PRIMARY KEY,"
            " recipient TEXT NOT NULL,"
            " student_account TEXT,"
            " text TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
        ),
    ),
)


class SemillaStore:
    """Durable state for SEMILLA."""

    def __init__(self, db: Database, clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(db, "semilla", _MIGRATIONS).run(clock)

    def add_account(
        self,
        *,
        account_id: str,
        zid: str | None,
        name: str,
        role: str,
        school: str | None,
        grade: str | None,
    ) -> dict[str, object]:
        if role not in ROLES:
            raise ValueError(f"unknown role: {role}")
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO semilla_accounts"
                " (account_id, zid, name, role, school, grade, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (account_id, zid, name, role, school, grade, now),
            )
        return self.get_account(account_id)

    def get_account(self, account_id: str) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM semilla_accounts WHERE account_id = ?",
            (account_id,),
        )
        if row is None:
            raise LookupError(f"unknown account: {account_id}")
        return self._account_row(row)

    def set_zid(self, *, account_id: str, zid: str) -> None:
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE semilla_accounts SET zid = ? WHERE account_id = ?",
                (zid, account_id),
            )

    def update_grade(self, *, account_id: str, new_grade: str) -> None:
        if new_grade not in GRADE_LEVELS:
            raise ValueError(f"unknown grade: {new_grade}")
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE semilla_accounts SET grade = ? WHERE account_id = ?",
                (new_grade, account_id),
            )

    def list_by_role(
        self, *, role: str, school: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        if school is not None:
            rows = self._db.query_all(
                "SELECT * FROM semilla_accounts"
                " WHERE role = ? AND school = ? ORDER BY created_at",
                (role, school),
            )
        else:
            rows = self._db.query_all(
                "SELECT * FROM semilla_accounts"
                " WHERE role = ? ORDER BY created_at",
                (role,),
            )
        return tuple(self._account_row(r) for r in rows)

    def add_grade(
        self,
        *,
        grade_id: str,
        student_account: str,
        subject: str,
        score: float,
        teacher_account: str,
    ) -> dict[str, object]:
        if not 0.0 <= score <= 10.0:
            raise ValueError("score must be 0..10")
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO semilla_grades"
                " (grade_id, student_account, subject, score,"
                " teacher_account, recorded_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (grade_id, student_account, subject, score, teacher_account, now),
            )
        return {
            "grade_id": grade_id,
            "student": student_account,
            "subject": subject,
            "score": score,
        }

    def grades_of(self, *, student_account: str) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM semilla_grades"
            " WHERE student_account = ? ORDER BY recorded_at",
            (student_account,),
        )
        return tuple(
            {"subject": str(r["subject"]), "score": float(r["score"])}
            for r in rows
        )

    def average_of(self, *, student_account: str) -> float | None:
        rows = self.grades_of(student_account=student_account)
        if not rows:
            return None
        return sum(float(r["score"]) for r in rows) / len(rows)

    def attendance_rate(self, *, student_account: str) -> float | None:
        rows = self._db.query_all(
            "SELECT present FROM semilla_attendance WHERE student_account = ?",
            (student_account,),
        )
        if not rows:
            return None
        return sum(int(r["present"]) for r in rows) / len(rows)

    def add_attendance(
        self, *, att_id: str, student_account: str, present: bool,
    ) -> None:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO semilla_attendance"
                " (att_id, student_account, present, recorded_at)"
                " VALUES (?, ?, ?, ?)",
                (att_id, student_account, int(present), now),
            )

    def add_welfare(
        self, *, welfare_id: str, student_account: str, mood: str,
    ) -> dict[str, object]:
        alert = mood in ("triste", "enojado", "enfermo")
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO semilla_welfare"
                " (welfare_id, student_account, mood, alert, recorded_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (welfare_id, student_account, mood, int(alert), now),
            )
        return {"welfare_id": welfare_id, "mood": mood, "alert": alert}

    def welfare_alerts(self) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM semilla_welfare"
            " WHERE alert = 1 ORDER BY recorded_at DESC"
        )
        return tuple(
            {"student": str(r["student_account"]), "mood": str(r["mood"])}
            for r in rows
        )

    def grant_scholarship(
        self, *, scholarship_id: str, student_account: str, reason: str,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO semilla_scholarships"
                " (scholarship_id, student_account, reason, granted_at)"
                " VALUES (?, ?, ?, ?)",
                (scholarship_id, student_account, reason, now),
            )
        return {
            "scholarship_id": scholarship_id,
            "student": student_account,
            "reason": reason,
        }

    def has_scholarship(self, *, student_account: str) -> bool:
        row = self._db.query_one(
            "SELECT 1 FROM semilla_scholarships WHERE student_account = ?",
            (student_account,),
        )
        return row is not None

    def summary(self, *, school: str | None = None) -> dict[str, object]:
        if school is not None:
            students = self._db.query_one(
                "SELECT COUNT(*) AS n FROM semilla_accounts"
                " WHERE role = 'alumno' AND school = ?",
                (school,),
            )
            teachers = self._db.query_one(
                "SELECT COUNT(*) AS n FROM semilla_accounts"
                " WHERE role = 'profesor' AND school = ?",
                (school,),
            )
        else:
            students = self._db.query_one(
                "SELECT COUNT(*) AS n FROM semilla_accounts"
                " WHERE role = 'alumno'"
            )
            teachers = self._db.query_one(
                "SELECT COUNT(*) AS n FROM semilla_accounts"
                " WHERE role = 'profesor'"
            )
        return {
            "students": int(students["n"]) if students is not None else 0,
            "teachers": int(teachers["n"]) if teachers is not None else 0,
        }

    def get_challenge_state(self, *, student_account: str) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM semilla_challenge_state WHERE student_account = ?",
            (student_account,),
        )
        if row is None:
            self.set_challenge_state(
                student_account=student_account,
                domain="matematicas",
                difficulty=1,
            )
            return {
                "student_account": student_account,
                "domain": "matematicas",
                "difficulty": 1,
            }
        return {
            "student_account": str(row["student_account"]),
            "domain": str(row["domain"]),
            "difficulty": int(row["difficulty"]),
        }

    def set_challenge_state(
        self, *, student_account: str, domain: str, difficulty: int,
    ) -> None:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT OR REPLACE INTO semilla_challenge_state"
                " (student_account, domain, difficulty, updated_at)"
                " VALUES (?, ?, ?, ?)",
                (student_account, domain, int(difficulty), now),
            )

    def record_attempt(
        self,
        *,
        attempt_id: str,
        student_account: str,
        domain: str,
        difficulty: int,
        correct: bool,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO semilla_attempts"
                " (attempt_id, student_account, domain, difficulty,"
                " correct, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    attempt_id,
                    student_account,
                    domain,
                    int(difficulty),
                    int(correct),
                    now,
                ),
            )
        return {
            "attempt_id": attempt_id,
            "correct": correct,
            "difficulty": int(difficulty),
        }

    def attempts_of(self, *, student_account: str) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM semilla_attempts"
            " WHERE student_account = ? ORDER BY created_at",
            (student_account,),
        )
        return tuple(
            {
                "attempt_id": str(r["attempt_id"]),
                "domain": str(r["domain"]),
                "difficulty": int(r["difficulty"]),
                "correct": bool(int(r["correct"])),
            }
            for r in rows
        )

    def detect_talents(
        self, *, student_account: str,
    ) -> tuple[dict[str, object], ...]:
        grades = self.grades_of(student_account=student_account)
        by_subject: dict = {}
        for g in grades:
            by_subject.setdefault(str(g["subject"]), []).append(float(g["score"]))
        new: list = []
        for subject, scores in by_subject.items():
            if len(scores) < 3:
                continue
            average = sum(scores) / len(scores)
            if average < 9.0:
                continue
            exists = self._db.query_one(
                "SELECT 1 FROM semilla_talents"
                " WHERE student_account = ? AND domain = ?",
                (student_account, subject),
            )
            if exists is not None:
                continue
            talent_id = "TAL-" + uuid.uuid4().hex[:10]
            evidence = f"promedio {average:.1f} en {len(scores)} notas"
            now = self._clock.now()
            with self._db.transaction() as cursor:
                cursor.execute(
                    "INSERT INTO semilla_talents"
                    " (talent_id, student_account, domain, evidence, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (talent_id, student_account, subject, evidence, now),
                )
            new.append(
                {
                    "talent_id": talent_id,
                    "domain": subject,
                    "evidence": evidence,
                }
            )
        return tuple(new)

    def list_talents(self, *, student_account: str) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM semilla_talents"
            " WHERE student_account = ? ORDER BY created_at",
            (student_account,),
        )
        return tuple(
            {
                "talent_id": str(r["talent_id"]),
                "domain": str(r["domain"]),
                "evidence": str(r["evidence"]),
            }
            for r in rows
        )

    def add_reward(
        self,
        *,
        reward_id: str,
        student_account: str,
        kind: str,
        detail: str | None,
        points: int,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO semilla_rewards"
                " (reward_id, student_account, kind, detail, points, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (reward_id, student_account, kind, detail, int(points), now),
            )
        return {"reward_id": reward_id, "kind": kind, "points": int(points)}

    def rewards_of(self, *, student_account: str) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM semilla_rewards"
            " WHERE student_account = ? ORDER BY created_at",
            (student_account,),
        )
        return tuple(
            {
                "reward_id": str(r["reward_id"]),
                "kind": str(r["kind"]),
                "detail": (
                    str(r["detail"]) if r["detail"] is not None else None
                ),
                "points": int(r["points"]),
            }
            for r in rows
        )

    def total_points(self, *, student_account: str) -> int:
        row = self._db.query_one(
            "SELECT SUM(points) AS total FROM semilla_rewards"
            " WHERE student_account = ?",
            (student_account,),
        )
        if row is None:
            return 0
        raw = row["total"]
        return int(raw) if raw is not None else 0

    def add_message(
        self,
        *,
        message_id: str,
        recipient: str,
        text: str,
        student_account: str | None = None,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO semilla_messages"
                " (message_id, recipient, student_account, text, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (message_id, recipient, student_account, text, now),
            )
        return {"message_id": message_id, "recipient": recipient, "text": text}

    def messages_of(self, *, recipient: str) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM semilla_messages"
            " WHERE recipient = ? ORDER BY created_at",
            (recipient,),
        )
        return tuple(
            {
                "message_id": str(r["message_id"]),
                "recipient": str(r["recipient"]),
                "text": str(r["text"]),
            }
            for r in rows
        )

    @staticmethod
    def _account_row(row) -> dict[str, object]:
        return {
            "account_id": str(row["account_id"]),
            "zid": str(row["zid"]) if row["zid"] is not None else None,
            "name": str(row["name"]),
            "role": str(row["role"]),
            "school": str(row["school"]) if row["school"] is not None else None,
            "grade": str(row["grade"]) if row["grade"] is not None else None,
            "created_at": float(row["created_at"]),
        }

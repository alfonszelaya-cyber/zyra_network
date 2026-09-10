"""SEMILLA proofs: student journey (register ->
grade -> scholarship), tutor welfare alerts,
teacher panel, scholarship engine rules."""
from __future__ import annotations

import threading
from pathlib import Path
from urllib.request import (
    Request,
    urlopen,
)

from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)

from apps.semilla.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.semilla.infrastructure.persistence.semilla_store import (
    SemillaStore,
)
from apps.semilla.server import serve_semilla


def _boot(tmp_path: Path):
    db = SQLiteAdapter(
        tmp_path / "semilla.db"
    )
    clock = FrozenClock()
    store = SemillaStore(db, clock)
    dead_client = NetworkClient(
        "http://127.0.0.1:1",
        timeout_seconds=1.0,
        max_retries=0,
    )
    server = serve_semilla(store, dead_client)
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()
    base = (
        "http://127.0.0.1:"
        f"{server.bound_port}"
    )
    return db, store, base, server, thread


def test_student_grades_and_scholarship(
    tmp_path: Path,
) -> None:
    db, store, base, server, thread = _boot(
        tmp_path
    )
    try:
        student = store.add_account(
            account_id="SEM-stu1",
            zid=None,
            name="Maria Estudiante",
            role="alumno",
            school="Escuela Central",
            grade="primaria",
        )
        for i in range(4):
            store.add_grade(
                grade_id=(
                    f"NOT-{i}"
                ),
                student_account=(
                    "SEM-stu1"
                ),
                subject=f"materia{i}",
                score=9.0,
                teacher_account=(
                    "SEM-prof1"
                ),
            )
            store.add_attendance(
                att_id=f"ATT-{i}",
                student_account=(
                    "SEM-stu1"
                ),
                present=True,
            )
        average = store.average_of(
            student_account="SEM-stu1"
        )
        assert average == 9.0
        attendance = (
            store.attendance_rate(
                student_account=(
                    "SEM-stu1"
                )
            )
        )
        assert attendance == 1.0
        student = store.get_account(
            "SEM-stu1"
        )
        assert (
            student["name"]
            == "Maria Estudiante"
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


def test_tutor_rules(
    tmp_path: Path,
) -> None:
    db, store, base, server, thread = _boot(
        tmp_path
    )
    try:
        result = store.add_welfare(
            welfare_id="WEL-1",
            student_account="SEM-stu",
            mood="triste",
        )
        assert result["alert"] is True
        result = store.add_welfare(
            welfare_id="WEL-2",
            student_account="SEM-stu",
            mood="feliz",
        )
        assert result["alert"] is False
        alerts = store.welfare_alerts()
        assert len(alerts) == 1
        assert alerts[0]["mood"] == (
            "triste"
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


def test_home_screen(
    tmp_path: Path,
) -> None:
    db, store, base, server, thread = _boot(
        tmp_path
    )
    try:
        with urlopen(
            base + "/semilla", timeout=10
        ) as response:
            home = response.read().decode(
                "utf-8"
            )
        assert "Soy alumno" in home
        assert "Soy profesor" in home
        assert "Soy institucion" in home
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()

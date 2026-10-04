
# client_validation_engine.py - NEXO / ZYRA (migrado mejorado)
from __future__ import annotations
import re
from typing import Dict, List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "client_validation_log", ("CREATE TABLE IF NOT EXISTS client_validation_log (validation_id TEXT PRIMARY KEY, action TEXT NOT NULL, result INTEGER NOT NULL, data_json TEXT NOT NULL, timestamp REAL NOT NULL)",)),
)

class ClientValidationEngine:
    """Motor de validación de clientes (persistente)."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.clientvalidation",
                        _MIGRATIONS).run(clock)

    def _audit(self, action: str, data: dict) -> None:
        import json as _j
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO client_validation_log"
                " (validation_id, action, result,"
                " data_json, timestamp)"
                " VALUES (?, ?, ?, ?, ?)",
                (f"CVAL-{uuid.uuid4()}", action,
                 0, _j.dumps(data, default=str), now))

    def validate_required_fields(self, client_data: Dict) -> bool:
        required = ("name", "document", "email")
        return all(
            f in client_data and client_data[f]
            for f in required)

    def validate_email(self, email: str) -> bool:
        pattern = r"^[^@]+@[^@]+\.[^@]+$"
        return bool(re.match(pattern, email or ""))

    def validate_document(self, document: str) -> bool:
        return len(str(document).strip()) >= 4

    def validate(self, client_data: Dict) -> bool:
        result = (
            self.validate_required_fields(client_data)
            and self.validate_email(
                client_data.get("email", ""))
            and self.validate_document(
                client_data.get("document", "")))
        self._audit("CLIENT_VALIDATION", {
            "client": client_data.get("document", "N/A"),
            "result": result})
        return result

    def validation_report(self, client_data: Dict) -> List[str]:
        issues = []
        if not client_data.get("name"):
            issues.append("Missing name")
        if not self.validate_document(
                client_data.get("document", "")):
            issues.append("Invalid document")
        if not self.validate_email(
                client_data.get("email", "")):
            issues.append("Invalid email")
        return issues

    def summary(self) -> Dict:
        row = self._db.query_one(
            "SELECT COUNT(*) AS n FROM client_validation_log")
        return {"audit_events":
                int(row["n"]) if row else 0,
                "generated_at": self._clock.now()}

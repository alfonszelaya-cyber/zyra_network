"""CICLO-DIGITAL durable store v2 - additive."""
from __future__ import annotations

import hashlib
import uuid

from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

_MIGRATIONS = (
    Migration(
        1,
        "ciclo",
        (
            "CREATE TABLE ciclo_recycled ("
            " item_id TEXT PRIMARY KEY,"
            " owner_zid TEXT NOT NULL,"
            " description TEXT NOT NULL,"
            " data_hash TEXT NOT NULL,"
            " token_amount INTEGER NOT"
            " NULL DEFAULT 0,"
            " document_id TEXT,"
            " synced INTEGER NOT NULL"
            " DEFAULT 0,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE ciclo_exports ("
            " export_id TEXT PRIMARY KEY,"
            " subject_zid TEXT NOT NULL,"
            " bundle_id TEXT NOT NULL,"
            " purpose TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
        ),
    ),
    Migration(
        2,
        "ciclo_global_archaeology",
        (
            "CREATE TABLE ciclo_global_recycling ("
            " event_id TEXT PRIMARY KEY,"
            " source_app TEXT NOT NULL,"
            " owner_zid TEXT NOT NULL,"
            " description TEXT NOT NULL,"
            " data_hash TEXT NOT NULL,"
            " category TEXT NOT NULL,"
            " condition_state TEXT NOT NULL,"
            " reward_tokens INTEGER NOT NULL,"
            " document_id TEXT,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE ciclo_arch_cases ("
            " case_id TEXT PRIMARY KEY,"
            " owner_zid TEXT NOT NULL,"
            " title TEXT NOT NULL,"
            " description TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " sealed_doc TEXT,"
            " created_at REAL NOT NULL,"
            " updated_at REAL NOT NULL)",
            "CREATE TABLE ciclo_findings ("
            " finding_id TEXT PRIMARY KEY,"
            " case_id TEXT NOT NULL,"
            " source TEXT NOT NULL,"
            " title TEXT NOT NULL,"
            " content TEXT NOT NULL,"
            " content_hash TEXT NOT NULL,"
            " certainty TEXT NOT NULL,"
            " reason TEXT,"
            " document_id TEXT,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE ciclo_reconstructions ("
            " reconstruction_id TEXT PRIMARY KEY,"
            " case_id TEXT NOT NULL,"
            " title TEXT NOT NULL,"
            " description TEXT NOT NULL,"
            " basis TEXT NOT NULL,"
            " certainty TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE ciclo_valuations ("
            " valuation_id TEXT PRIMARY KEY,"
            " item_id TEXT NOT NULL,"
            " category TEXT NOT NULL,"
            " condition TEXT NOT NULL,"
            " estimated_value REAL NOT NULL,"
            " reward_tokens INTEGER NOT NULL,"
            " created_at REAL NOT NULL)",
        ),
    ),
)

CERTAINTY_LEVELS = (
    "evidencia_encontrada",
    "evidencia_verificada",
    "reconstruccion",
    "inferencia",
    "incertidumbre",
)

CATEGORIES = (
    "foto",
    "video",
    "documento",
    "datos",
    "otro",
)

SOURCE_APPS = (
    "rep",
    "nexo",
    "agro",
    "semilla",
    "mpe",
    "subastas",
    "axis",
    "ciclo",
)

BASE_VALUES = {
    "foto": 3.0,
    "video": 8.0,
    "documento": 5.0,
    "datos": 4.0,
    "otro": 2.0,
}

CONDITION_FACTORS = {
    "bueno": 1.0,
    "regular": 0.7,
    "malo": 0.4,
}


def value_of(category: str, condition: str) -> float:
    return round(
        BASE_VALUES[category]
        * CONDITION_FACTORS[condition],
        2,
    )


def reward_of(estimated: float) -> int:
    return max(1, int(estimated // 2))


class CicloStore:
    def __init__(self, db: Database, clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db, "ciclo", _MIGRATIONS
        ).run(clock)

    def add_recycled(
        self,
        *,
        item_id: str,
        owner_zid: str,
        description: str,
        data_hash: str,
        token_amount: int,
        document_id: str | None,
        synced: bool,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO ciclo_recycled"
                " (item_id, owner_zid,"
                "  description, data_hash,"
                "  token_amount,"
                "  document_id, synced,"
                "  created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item_id,
                    owner_zid,
                    description,
                    data_hash,
                    token_amount,
                    document_id,
                    int(synced),
                    now,
                ),
            )
        return self.get_recycled(item_id)

    def get_recycled(self, item_id: str) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM ciclo_recycled WHERE item_id = ?",
            (item_id,),
        )
        if row is None:
            raise LookupError(
                f"unknown recycled item: {item_id}"
            )
        doc = row["document_id"]
        return {
            "item_id": str(row["item_id"]),
            "owner_zid": str(row["owner_zid"]),
            "description": str(row["description"]),
            "data_hash": str(row["data_hash"]),
            "token_amount": int(row["token_amount"]),
            "document_id": (
                str(doc) if doc is not None else None
            ),
            "synced": bool(int(row["synced"])),
        }

    def list_recycled(
        self, *, owner_zid: str,
    ) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM ciclo_recycled"
            " WHERE owner_zid = ? ORDER BY created_at",
            (owner_zid,),
        )
        return tuple(
            self.get_recycled(str(r["item_id"]))
            for r in rows
        )

    def record_export(
        self,
        *,
        export_id: str,
        subject_zid: str,
        bundle_id: str,
        purpose: str,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO ciclo_exports"
                " (export_id, subject_zid, bundle_id,"
                "  purpose, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (export_id, subject_zid, bundle_id, purpose, now),
            )
        return {
            "export_id": export_id,
            "subject_zid": subject_zid,
            "bundle_id": bundle_id,
            "purpose": purpose,
        }

    def add_global_recycling(
        self,
        *,
        event_id: str,
        source_app: str,
        owner_zid: str,
        description: str,
        category: str,
        condition_state: str,
        document_id: str | None,
    ) -> dict[str, object]:
        if source_app not in SOURCE_APPS:
            raise ValueError(
                f"unknown source app: {source_app}"
            )
        if category not in CATEGORIES:
            raise ValueError(
                f"unknown category: {category}"
            )
        data_hash = hashlib.sha256(
            (
                source_app
                + "|"
                + owner_zid
                + "|"
                + description
            ).encode("utf-8")
        ).hexdigest()
        estimated = value_of(
            category, condition_state
        )
        reward = reward_of(estimated)
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO ciclo_global_recycling ("
                " event_id, source_app, owner_zid,"
                "  description, data_hash, category,"
                "  condition_state, reward_tokens,"
                "  document_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    source_app,
                    owner_zid,
                    description,
                    data_hash,
                    category,
                    condition_state,
                    reward,
                    document_id,
                    now,
                ),
            )
        return {
            "event_id": event_id,
            "source_app": source_app,
            "data_hash": data_hash,
            "category": category,
            "estimated_value": estimated,
            "reward_tokens": reward,
        }

    def global_recycling_stats(self) -> dict[str, object]:
        rows = self._db.query_all(
            "SELECT source_app, COUNT(*) AS n,"
            " SUM(reward_tokens) AS tokens"
            " FROM ciclo_global_recycling"
            " GROUP BY source_app"
        )
        by_app = {}
        total = 0
        for row in rows:
            by_app[str(row["source_app"])] = int(row["n"])
            total += int(row["tokens"] or 0)
        return {
            "by_app": by_app,
            "total_events": sum(by_app.values()),
            "total_tokens_awarded": total,
        }

    def create_arch_case(
        self,
        *,
        case_id: str,
        owner_zid: str,
        title: str,
        description: str,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO ciclo_arch_cases"
                " (case_id, owner_zid, title, description,"
                "  status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 'open', ?, ?)",
                (case_id, owner_zid, title, description, now, now),
            )
        return self.get_arch_case(case_id)

    def get_arch_case(self, case_id: str) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM ciclo_arch_cases WHERE case_id = ?",
            (case_id,),
        )
        if row is None:
            raise LookupError(
                f"unknown archaeology case: {case_id}"
            )
        findings = self._db.query_all(
            "SELECT finding_id, title, certainty,"
            " content_hash FROM ciclo_findings"
            " WHERE case_id = ? ORDER BY created_at",
            (case_id,),
        )
        reconstructions = self._db.query_all(
            "SELECT reconstruction_id, title, certainty"
            " FROM ciclo_reconstructions"
            " WHERE case_id = ? ORDER BY created_at",
            (case_id,),
        )
        return {
            "case_id": str(row["case_id"]),
            "owner_zid": str(row["owner_zid"]),
            "title": str(row["title"]),
            "description": str(row["description"]),
            "status": str(row["status"]),
            "sealed_doc": (
                str(row["sealed_doc"])
                if row["sealed_doc"] is not None
                else None
            ),
            "findings": [
                {
                    "finding_id": str(f["finding_id"]),
                    "title": str(f["title"]),
                    "certainty": str(f["certainty"]),
                    "content_hash": str(f["content_hash"]),
                }
                for f in findings
            ],
            "reconstructions": [
                {
                    "reconstruction_id": str(
                        r["reconstruction_id"]
                    ),
                    "title": str(r["title"]),
                    "certainty": str(r["certainty"]),
                }
                for r in reconstructions
            ],
        }

    def add_finding(
        self,
        *,
        finding_id: str,
        case_id: str,
        source: str,
        title: str,
        content: str,
        certainty: str,
        reason: str | None,
        document_id: str | None,
    ) -> dict[str, object]:
        if certainty not in CERTAINTY_LEVELS:
            raise ValueError(f"unknown certainty: {certainty}")
        row = self._db.query_one(
            "SELECT case_id FROM ciclo_arch_cases"
            " WHERE case_id = ?",
            (case_id,),
        )
        if row is None:
            raise LookupError(
                f"unknown archaeology case: {case_id}"
            )
        content_hash = hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO ciclo_findings"
                " (finding_id, case_id, source, title,"
                "  content, content_hash, certainty, reason,"
                "  document_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    finding_id,
                    case_id,
                    source,
                    title,
                    content,
                    content_hash,
                    certainty,
                    reason,
                    document_id,
                    now,
                ),
            )
        return {
            "finding_id": finding_id,
            "content_hash": content_hash,
            "certainty": certainty,
        }

    def add_reconstruction(
        self,
        *,
        reconstruction_id: str,
        case_id: str,
        title: str,
        description: str,
        basis: str,
        certainty: str,
    ) -> dict[str, object]:
        if certainty not in CERTAINTY_LEVELS:
            raise ValueError(f"unknown certainty: {certainty}")
        row = self._db.query_one(
            "SELECT case_id FROM ciclo_arch_cases"
            " WHERE case_id = ?",
            (case_id,),
        )
        if row is None:
            raise LookupError(
                f"unknown archaeology case: {case_id}"
            )
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO ciclo_reconstructions"
                " (reconstruction_id, case_id, title,"
                "  description, basis, certainty, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    reconstruction_id,
                    case_id,
                    title,
                    description,
                    basis,
                    certainty,
                    now,
                ),
            )
        return {
            "reconstruction_id": reconstruction_id,
            "certainty": certainty,
        }

    def seal_arch_case(
        self,
        *,
        case_id: str,
        sealed_doc: str,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE ciclo_arch_cases"
                " SET status = 'sealed', sealed_doc = ?,"
                " updated_at = ? WHERE case_id = ?",
                (sealed_doc, now, case_id),
            )
        return self.get_arch_case(case_id)

    def add_valuation(
        self,
        *,
        valuation_id: str,
        item_id: str,
        category: str,
        condition: str,
    ) -> dict[str, object]:
        if category not in CATEGORIES:
            raise ValueError(f"unknown category: {category}")
        estimated = value_of(category, condition)
        reward = reward_of(estimated)
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO ciclo_valuations"
                " (valuation_id, item_id, category,"
                "  condition, estimated_value, reward_tokens,"
                "  created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    valuation_id,
                    item_id,
                    category,
                    condition,
                    estimated,
                    reward,
                    now,
                ),
            )
        return {
            "valuation_id": valuation_id,
            "estimated_value": estimated,
            "reward_tokens": reward,
        }

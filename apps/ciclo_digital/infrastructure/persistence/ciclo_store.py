"""CICLO-DIGITAL durable store."""
from __future__ import annotations

from shared_engines.storage.database import (
    Database,
)
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
)


class CicloStore:
    def __init__(
        self, db: Database, clock
    ) -> None:
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
                " VALUES (?, ?, ?, ?, ?, ?,"
                "  ?, ?)",
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

    def get_recycled(
        self, item_id: str
    ) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM ciclo_recycled"
            " WHERE item_id = ?",
            (item_id,),
        )
        if row is None:
            raise LookupError(
                "unknown recycled item:"
                f" {item_id}"
            )
        doc = row["document_id"]
        return {
            "item_id": str(
                row["item_id"]
            ),
            "owner_zid": str(
                row["owner_zid"]
            ),
            "description": str(
                row["description"]
            ),
            "data_hash": str(
                row["data_hash"]
            ),
            "token_amount": int(
                row["token_amount"]
            ),
            "document_id": (
                str(doc)
                if doc is not None
                else None
            ),
            "synced": bool(
                int(row["synced"])
            ),
        }

    def list_recycled(
        self, *, owner_zid: str
    ) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM ciclo_recycled"
            " WHERE owner_zid = ?"
            " ORDER BY created_at",
            (owner_zid,),
        )
        return tuple(
            self.get_recycled(
                str(r["item_id"])
            )
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
                " (export_id, subject_zid,"
                "  bundle_id, purpose,"
                "  created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    export_id,
                    subject_zid,
                    bundle_id,
                    purpose,
                    now,
                ),
            )
        return {
            "export_id": export_id,
            "subject_zid": subject_zid,
            "bundle_id": bundle_id,
            "purpose": purpose,
        }

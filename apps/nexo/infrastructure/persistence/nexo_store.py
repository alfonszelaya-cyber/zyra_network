"""NexoCore durable ledger: hash-chained
accounting between ZIDs. Fiscal kinds only -
import/export live in MERCADO."""
from __future__ import annotations

import hashlib

from shared_engines.storage.database import (
    Database,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

KINDS = (
    "venta",
    "compra",
    "pago",
    "cobro",
    "ajuste",
)

_MIGRATIONS = (
    Migration(
        1,
        "nexo",
        (
            "CREATE TABLE nexo_companies ("
            " company_id TEXT PRIMARY KEY,"
            " zid TEXT,"
            " name TEXT NOT NULL,"
            " synced INTEGER NOT NULL"
            " DEFAULT 0,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE nexo_operations ("
            " seq INTEGER PRIMARY KEY"
            " AUTOINCREMENT,"
            " operation_id TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " seller_zid TEXT NOT NULL,"
            " buyer_zid TEXT NOT NULL,"
            " amount REAL NOT NULL,"
            " description TEXT NOT NULL,"
            " invoice_id TEXT,"
            " entry_hash TEXT NOT NULL,"
            " prev_hash TEXT NOT NULL,"
            " synced INTEGER NOT NULL"
            " DEFAULT 0,"
            " created_at REAL NOT NULL)",
            "CREATE INDEX nexo_seq"
            " ON nexo_operations (seq)",
        ),
    ),
)


def _entry_hash(
    *,
    seq: int,
    kind: str,
    seller_zid: str,
    buyer_zid: str,
    amount: float,
    description: str,
    prev_hash: str,
    created_at: float,
) -> str:
    raw = (
        str(seq)
        + "|"
        + kind
        + "|"
        + seller_zid
        + "|"
        + buyer_zid
        + "|"
        + str(amount)
        + "|"
        + description
        + "|"
        + str(created_at)
        + "|"
        + prev_hash
    )
    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


class NexoStore:
    """Hash-chained durable ledger."""

    def __init__(
        self, db: Database, clock
    ) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db, "nexo", _MIGRATIONS
        ).run(clock)

    def add_company(
        self,
        *,
        company_id: str,
        zid: str | None,
        name: str,
        synced: bool,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_companies"
                " (company_id, zid, name,"
                "  synced, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    company_id,
                    zid,
                    name,
                    int(synced),
                    now,
                ),
            )
        return self.get_company(company_id)

    def get_company(
        self, company_id: str
    ) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM nexo_companies"
            " WHERE company_id = ?",
            (company_id,),
        )
        if row is None:
            raise LookupError(
                "unknown company:"
                f" {company_id}"
            )
        zid = row["zid"]
        return {
            "company_id": str(
                row["company_id"]
            ),
            "zid": (
                str(zid)
                if zid is not None
                else None
            ),
            "name": str(row["name"]),
            "synced": bool(
                int(row["synced"])
            ),
        }

    def record_operation(
        self,
        *,
        operation_id: str,
        kind: str,
        seller_zid: str,
        buyer_zid: str,
        amount: float,
        description: str,
        invoice_id: str | None,
        synced: bool,
    ) -> dict[str, object]:
        if kind not in KINDS:
            raise ValueError(
                f"unknown kind: {kind}"
            )
        if amount <= 0:
            raise ValueError(
                "amount must be positive"
            )
        now = self._clock.now()
        with self._db.transaction() as cursor:
            last = cursor.execute(
                "SELECT seq, entry_hash"
                " FROM nexo_operations"
                " ORDER BY seq DESC"
                " LIMIT 1"
            ).fetchone()
            if last is None:
                seq = 1
                prev_hash = "GENESIS"
            else:
                seq = int(
                    last["seq"]
                ) + 1
                prev_hash = str(
                    last["entry_hash"]
                )
            entry_hash = _entry_hash(
                seq=seq,
                kind=kind,
                seller_zid=seller_zid,
                buyer_zid=buyer_zid,
                amount=amount,
                description=description,
                prev_hash=prev_hash,
                created_at=now,
            )
            cursor.execute(
                "INSERT INTO nexo_operations"
                " (operation_id, kind,"
                "  seller_zid, buyer_zid,"
                "  amount, description,"
                "  invoice_id, entry_hash,"
                "  prev_hash, synced,"
                "  created_at)"
                " VALUES (?, ?, ?, ?, ?,"
                "  ?, ?, ?, ?, ?, ?, ?)",
                (
                    operation_id,
                    kind,
                    seller_zid,
                    buyer_zid,
                    amount,
                    description,
                    invoice_id,
                    entry_hash,
                    prev_hash,
                    int(synced),
                    now,
                ),
            )
        return {
            "operation_id": (
                operation_id
            ),
            "seq": seq,
            "kind": kind,
            "amount": amount,
            "entry_hash": entry_hash,
            "prev_hash": prev_hash,
            "invoice_id": invoice_id,
            "synced": synced,
        }

    def verify_chain(self) -> bool:
        rows = self._db.query_all(
            "SELECT * FROM nexo_operations"
            " ORDER BY seq"
        )
        prev = "GENESIS"
        for r in rows:
            expected = _entry_hash(
                seq=int(r["seq"]),
                kind=str(r["kind"]),
                seller_zid=str(
                    r["seller_zid"]
                ),
                buyer_zid=str(
                    r["buyer_zid"]
                ),
                amount=float(
                    r["amount"]
                ),
                description=str(
                    r["description"]
                ),
                prev_hash=prev,
                created_at=float(
                    r["created_at"]
                ),
            )
            if (
                str(r["entry_hash"])
                != expected
                or str(r["prev_hash"])
                != prev
            ):
                return False
            prev = str(r["entry_hash"])
        return True

    def list_operations(
        self,
    ) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_operations"
            " ORDER BY seq"
        )
        return tuple(
            {
                "seq": int(r["seq"]),
                "kind": str(r["kind"]),
                "seller_zid": str(
                    r["seller_zid"]
                ),
                "buyer_zid": str(
                    r["buyer_zid"]
                ),
                "amount": float(
                    r["amount"]
                ),
                "invoice_id": (
                    str(r["invoice_id"])
                    if r["invoice_id"]
                    is not None
                    else None
                ),
                "entry_hash": str(
                    r["entry_hash"]
                ),
            }
            for r in rows
        )

    def summary(self) -> dict[str, object]:
        totals = self._db.query_all(
            "SELECT kind, COUNT(*) AS n,"
            " SUM(amount) AS total FROM"
            " nexo_operations"
            " GROUP BY kind"
            " ORDER BY kind"
        )
        by_kind = {
            str(r["kind"]): {
                "count": int(r["n"]),
                "total": float(
                    r["total"]
                ),
            }
            for r in totals
        }
        row = self._db.query_one(
            "SELECT COUNT(*) AS n FROM"
            " nexo_operations"
        )
        return {
            "operations_total": int(
                row["n"]
            )
            if row is not None
            else 0,
            "by_kind": by_kind,
            "chain_intact": (
                self.verify_chain()
            ),
        }

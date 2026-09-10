"""AGRO local durable store v2 (role-aware)."""
from __future__ import annotations

from shared_engines.storage.database import (
    Database,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

ROLES = (
    "agricultor",
    "ganadero",
    "gobierno",
    "banco",
)

_MIGRATIONS = (
    Migration(
        2,
        "agro",
        (
            "CREATE TABLE IF NOT EXISTS"
            " agro_producers_v2 ("
            " producer_id TEXT PRIMARY KEY,"
            " zid TEXT,"
            " name TEXT NOT NULL,"
            " producer_type TEXT NOT NULL,"
            " role TEXT NOT NULL"
            " DEFAULT 'agricultor',"
            " location TEXT,"
            " verified INTEGER NOT NULL"
            " DEFAULT 0,"
            " synced INTEGER NOT NULL"
            " DEFAULT 0,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE"
            " agro_productions ("
            " production_id TEXT PRIMARY"
            " KEY,"
            " producer_id TEXT NOT NULL,"
            " product TEXT NOT NULL,"
            " quantity REAL NOT NULL,"
            " unit TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " network_seq INTEGER,"
            " created_at REAL NOT NULL)",
        ),
    ),
)


class AgroStore:
    """Durable local state for AGRO (v2, roles)."""

    def __init__(
        self, db: Database, clock
    ) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db, "agro.store", _MIGRATIONS
        ).run(clock)

    def add_producer(
        self,
        *,
        producer_id: str,
        zid: str | None,
        name: str,
        producer_type: str,
        role: str,
        location: str | None,
        synced: bool,
    ) -> dict[str, object]:
        if role not in ROLES:
            raise ValueError(
                f"unknown role: {role}"
            )
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO agro_producers_v2"
                " (producer_id, zid, name,"
                "  producer_type, role,"
                "  location, verified, synced,"
                "  created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 0,"
                "  ?, ?)",
                (
                    producer_id,
                    zid,
                    name,
                    producer_type,
                    role,
                    location,
                    int(synced),
                    now,
                ),
            )
        return self.get_producer(
            producer_id
        )

    def link_zid(
        self, *, producer_id: str, zid: str
    ) -> None:
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE agro_producers_v2 SET"
                " zid = ?, synced = 1"
                " WHERE producer_id = ?",
                (zid, producer_id),
            )

    def mark_verified(
        self, *, producer_id: str
    ) -> None:
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE agro_producers_v2 SET"
                " verified = 1"
                " WHERE producer_id = ?",
                (producer_id,),
            )

    def get_producer(
        self, producer_id: str
    ) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM"
            " agro_producers_v2"
            " WHERE producer_id = ?",
            (producer_id,),
        )
        if row is None:
            raise LookupError(
                "unknown producer:"
                f" {producer_id}"
            )
        return self._producer_row(row)

    def list_producers(
        self, *, role: str | None = None
    ) -> tuple[dict[str, object], ...]:
        if role is not None:
            if role not in ROLES:
                raise ValueError(
                    f"unknown role:"
                    f" {role}"
                )
            rows = self._db.query_all(
                "SELECT * FROM"
                " agro_producers_v2"
                " WHERE role = ?"
                " ORDER BY created_at",
                (role,),
            )
        else:
            rows = self._db.query_all(
                "SELECT * FROM"
                " agro_producers_v2"
                " ORDER BY created_at"
            )
        return tuple(
            self._producer_row(r)
            for r in rows
        )

    def add_production(
        self,
        *,
        production_id: str,
        producer_id: str,
        product: str,
        quantity: float,
        unit: str,
        network_seq: int | None,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO agro_productions"
                " (production_id,"
                "  producer_id, product,"
                "  quantity, unit, status,"
                "  network_seq, created_at)"
                " VALUES (?, ?, ?, ?, ?,"
                "  'active', ?, ?)",
                (
                    production_id,
                    producer_id,
                    product,
                    quantity,
                    unit,
                    network_seq,
                    now,
                ),
            )
        row = self._db.query_one(
            "SELECT * FROM agro_productions"
            " WHERE production_id = ?",
            (production_id,),
        )
        assert row is not None
        raw_seq = row["network_seq"]
        return {
            "production_id": str(
                row["production_id"]
            ),
            "producer_id": str(
                row["producer_id"]
            ),
            "product": str(row["product"]),
            "quantity": float(
                row["quantity"]
            ),
            "unit": str(row["unit"]),
            "status": str(row["status"]),
            "network_seq": (
                int(raw_seq)
                if raw_seq is not None
                else None
            ),
        }

    def list_productions(
        self,
    ) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM agro_productions"
            " ORDER BY created_at"
        )
        result: list[
            dict[str, object]
        ] = []
        for r in rows:
            raw_seq = r["network_seq"]
            result.append(
                {
                    "production_id": str(
                        r["production_id"]
                    ),
                    "producer_id": str(
                        r["producer_id"]
                    ),
                    "product": str(
                        r["product"]
                    ),
                    "quantity": float(
                        r["quantity"]
                    ),
                    "unit": str(r["unit"]),
                    "status": str(
                        r["status"]
                    ),
                    "network_seq": (
                        int(raw_seq)
                        if raw_seq
                        is not None
                        else None
                    ),
                }
            )
        return tuple(result)

    def summary(self) -> dict[str, object]:
        producers = self._db.query_one(
            "SELECT COUNT(*) AS total,"
            " SUM(verified) AS verified"
            " FROM agro_producers_v2"
        )
        by_role_rows = self._db.query_all(
            "SELECT role, COUNT(*) AS n"
            " FROM agro_producers_v2"
            " GROUP BY role"
        )
        productions = self._db.query_all(
            "SELECT product, SUM(quantity)"
            " AS total FROM"
            " agro_productions"
            " GROUP BY product"
            " ORDER BY product"
        )
        by_role = {
            str(r["role"]): int(r["n"])
            for r in by_role_rows
        }
        by_product = {
            str(r["product"]): float(
                r["total"]
            )
            for r in productions
        }
        total = 0
        verified = 0
        if producers is not None:
            total = int(
                producers["total"]
            )
            if (
                producers["verified"]
                is not None
            ):
                verified = int(
                    producers["verified"]
                )
        return {
            "producers_total": total,
            "producers_verified": (
                verified
            ),
            "producers_by_role": by_role,
            "productions_by_product": (
                by_product
            ),
        }

    @staticmethod
    def _producer_row(row) -> dict[str, object]:
        return {
            "producer_id": str(
                row["producer_id"]
            ),
            "zid": (
                str(row["zid"])
                if row["zid"] is not None
                else None
            ),
            "name": str(row["name"]),
            "producer_type": str(
                row["producer_type"]
            ),
            "role": str(row["role"]),
            "location": (
                str(row["location"])
                if row["location"]
                is not None
                else None
            ),
            "verified": bool(
                int(row["verified"])
            ),
            "synced": bool(
                int(row["synced"])
            ),
            "created_at": float(
                row["created_at"]
            ),
        }

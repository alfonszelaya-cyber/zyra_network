"""AGRO local durable store v3 (role-aware +
government aid lifecycle). Additive on v2."""
from __future__ import annotations

import uuid

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
    Migration(
        3,
        "agro_aid",
        (
            "CREATE TABLE IF NOT EXISTS"
            " agro_aid_requests ("
            " aid_id TEXT PRIMARY KEY,"
            " producer_id TEXT NOT NULL,"
            " zid TEXT,"
            " program TEXT NOT NULL,"
            " item TEXT NOT NULL,"
            " quantity REAL NOT NULL,"
            " status TEXT NOT NULL"
            " DEFAULT 'requested',"
            " eligibility TEXT,"
            " created_at REAL NOT NULL,"
            " updated_at REAL NOT NULL)",
            "CREATE TABLE IF NOT EXISTS"
            " agro_aid_events ("
            " event_id TEXT PRIMARY KEY,"
            " aid_id TEXT NOT NULL,"
            " transition TEXT NOT NULL,"
            " actor TEXT NOT NULL,"
            " detail TEXT,"
            " network_seq INTEGER,"
            " created_at REAL NOT NULL)",
        ),
    ),
)


class AgroStore:
    """Durable local state for AGRO (v3)."""

    def __init__(
        self, db: Database, clock
    ) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db,
            "agro.store",
            _MIGRATIONS,
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
                "INSERT INTO"
                " agro_producers_v2"
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
        self,
        *,
        producer_id: str,
        zid: str,
    ) -> None:
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE"
                " agro_producers_v2 SET"
                " zid = ?, synced = 1"
                " WHERE producer_id = ?",
                (zid, producer_id),
            )

    def mark_verified(
        self, *, producer_id: str
    ) -> None:
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE"
                " agro_producers_v2 SET"
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
        self,
        *,
        role: str | None = None,
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
                "INSERT INTO"
                " agro_productions"
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
            "SELECT * FROM"
            " agro_productions"
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
            "product": str(
                row["product"]
            ),
            "quantity": float(
                row["quantity"]
            ),
            "unit": str(row["unit"]),
            "status": str(
                row["status"]
            ),
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
            "SELECT * FROM"
            " agro_productions"
            " ORDER BY created_at"
        )
        result: list[
            dict[str, object]
        ] = []
        for r in rows:
            raw_seq = r["network_seq"]
            result.append(
                {
                    "production_id": (
                        str(
                            r[
                                "production_id"
                            ]
                        )
                    ),
                    "producer_id": (
                        str(
                            r[
                                "producer_id"
                            ]
                        )
                    ),
                    "product": str(
                        r["product"]
                    ),
                    "quantity": float(
                        r["quantity"]
                    ),
                    "unit": str(
                        r["unit"]
                    ),
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

    def summary(
        self,
    ) -> dict[str, object]:
        producers = (
            self._db.query_one(
                "SELECT COUNT(*) AS"
                " total,"
                " SUM(verified) AS"
                " verified"
                " FROM"
                " agro_producers_v2"
            )
        )
        by_role_rows = (
            self._db.query_all(
                "SELECT role, COUNT(*)"
                " AS n FROM"
                " agro_producers_v2"
                " GROUP BY role"
            )
        )
        productions = (
            self._db.query_all(
                "SELECT product,"
                " SUM(quantity) AS total"
                " FROM"
                " agro_productions"
                " GROUP BY product"
                " ORDER BY product"
            )
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
                    producers[
                        "verified"
                    ]
                )
        aid = self.aid_summary()
        return {
            "producers_total": total,
            "producers_verified": (
                verified
            ),
            "producers_by_role": (
                by_role
            ),
            "productions_by_product": (
                by_product
            ),
            "aid_total": aid[
                "aid_total"
            ],
            "aid_by_status": aid[
                "aid_by_status"
            ],
            "aid_by_program": aid[
                "aid_by_program"
            ],
        }

    @staticmethod
    def _producer_row(
        row,
    ) -> dict[str, object]:
        return {
            "producer_id": str(
                row["producer_id"]
            ),
            "zid": (
                str(row["zid"])
                if row["zid"]
                is not None
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

    def _record_aid_event(
        self,
        *,
        aid_id: str,
        transition: str,
        actor: str,
        detail: str | None,
        network_seq: int | None,
    ) -> None:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " agro_aid_events"
                " (event_id, aid_id,"
                "  transition, actor,"
                "  detail, network_seq,"
                "  created_at)"
                " VALUES (?, ?, ?, ?,"
                "  ?, ?, ?)",
                (
                    "AEV-"
                    + uuid.uuid4().hex[
                        :10
                    ],
                    aid_id,
                    transition,
                    actor,
                    detail,
                    network_seq,
                    now,
                ),
            )

    def _aid_row(self, aid_id: str):
        return self._db.query_one(
            "SELECT * FROM"
            " agro_aid_requests"
            " WHERE aid_id = ?",
            (aid_id,),
        )

    def create_aid_request(
        self,
        *,
        aid_id: str,
        producer_id: str,
        program: str,
        item: str,
        quantity: float,
        network_seq: int | None,
    ) -> dict[str, object]:
        producer = self.get_producer(
            producer_id
        )
        dup = self._db.query_one(
            "SELECT 1 FROM"
            " agro_aid_requests WHERE"
            " producer_id = ? AND"
            " program = ?",
            (producer_id, program),
        )
        if dup is not None:
            raise ValueError(
                "aid already requested"
                " for this program"
            )
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " agro_aid_requests ("
                " aid_id, producer_id,"
                " zid, program, item,"
                " quantity, status,"
                " eligibility, created_at,"
                " updated_at)"
                " VALUES (?, ?, ?, ?, ?,"
                "  ?, 'requested', NULL,"
                "  ?, ?)",
                (
                    aid_id,
                    producer_id,
                    producer.get("zid"),
                    program,
                    item,
                    float(quantity),
                    now,
                    now,
                ),
            )
        self._record_aid_event(
            aid_id=aid_id,
            transition=(
                "AID_REQUESTED"
            ),
            actor="productor",
            detail=(
                program + ": " + item
            ),
            network_seq=network_seq,
        )
        return self.get_aid(aid_id)

    def evaluate_aid(
        self,
        *,
        aid_id: str,
        eligible: bool,
        reason: str,
        network_seq: int | None,
    ) -> dict[str, object]:
        row = self._aid_row(aid_id)
        if row is None:
            raise LookupError(
                "unknown aid:"
                f" {aid_id}"
            )
        if str(row["status"]) != (
            "requested"
        ):
            raise ValueError(
                "aid not awaiting"
                " eligibility"
            )
        new_status = (
            "eligible"
            if eligible
            else "rejected"
        )
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE"
                " agro_aid_requests SET"
                " status = ?,"
                " eligibility = ?,"
                " updated_at = ?"
                " WHERE aid_id = ?",
                (
                    new_status,
                    reason,
                    self._clock.now(),
                    aid_id,
                ),
            )
        self._record_aid_event(
            aid_id=aid_id,
            transition=(
                "AID_ELIGIBILITY_"
                "EVALUATED"
            ),
            actor="gobierno",
            detail=reason,
            network_seq=network_seq,
        )
        return self.get_aid(aid_id)

    def _transition(
        self,
        *,
        aid_id: str,
        expected_from: str,
        to_status: str,
        transition: str,
        actor: str,
        detail: str | None,
        network_seq: int | None,
    ) -> dict[str, object]:
        row = self._aid_row(aid_id)
        if row is None:
            raise LookupError(
                "unknown aid:"
                f" {aid_id}"
            )
        current = str(row["status"])
        if current != expected_from:
            raise ValueError(
                f"aid status is"
                f" {current}, expected"
                f" {expected_from}"
            )
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE"
                " agro_aid_requests SET"
                " status = ?,"
                " updated_at = ?"
                " WHERE aid_id = ?",
                (
                    to_status,
                    self._clock.now(),
                    aid_id,
                ),
            )
        self._record_aid_event(
            aid_id=aid_id,
            transition=transition,
            actor=actor,
            detail=detail,
            network_seq=network_seq,
        )
        return self.get_aid(aid_id)

    def approve_aid(
        self,
        *,
        aid_id: str,
        network_seq: int | None,
    ) -> dict[str, object]:
        return self._transition(
            aid_id=aid_id,
            expected_from="eligible",
            to_status="approved",
            transition="AID_APPROVED",
            actor="gobierno",
            detail=None,
            network_seq=network_seq,
        )

    def assign_aid(
        self,
        *,
        aid_id: str,
        detail: str | None,
        network_seq: int | None,
    ) -> dict[str, object]:
        return self._transition(
            aid_id=aid_id,
            expected_from="approved",
            to_status="assigned",
            transition="AID_ASSIGNED",
            actor="gobierno",
            detail=detail,
            network_seq=network_seq,
        )

    def deliver_aid(
        self,
        *,
        aid_id: str,
        detail: str | None,
        network_seq: int | None,
    ) -> dict[str, object]:
        return self._transition(
            aid_id=aid_id,
            expected_from="assigned",
            to_status="delivered",
            transition=(
                "AID_DELIVERED"
            ),
            actor="gobierno",
            detail=detail,
            network_seq=network_seq,
        )

    def confirm_aid(
        self,
        *,
        aid_id: str,
        network_seq: int | None,
    ) -> dict[str, object]:
        return self._transition(
            aid_id=aid_id,
            expected_from=(
                "delivered"
            ),
            to_status="confirmed",
            transition=(
                "AID_DELIVERY_"
                "CONFIRMED"
            ),
            actor="productor",
            detail=None,
            network_seq=network_seq,
        )

    def get_aid(
        self, aid_id: str,
    ) -> dict[str, object]:
        row = self._aid_row(aid_id)
        if row is None:
            raise LookupError(
                "unknown aid:"
                f" {aid_id}"
            )
        events = self._db.query_all(
            "SELECT * FROM"
            " agro_aid_events WHERE"
            " aid_id = ?"
            " ORDER BY created_at,"
            " rowid",
            (aid_id,),
        )
        event_list = []
        for e in events:
            seq = e["network_seq"]
            event_list.append(
                {
                    "event_id": str(
                        e["event_id"]
                    ),
                    "transition": str(
                        e[
                            "transition"
                        ]
                    ),
                    "actor": str(
                        e["actor"]
                    ),
                    "detail": (
                        str(
                            e["detail"]
                        )
                        if e["detail"]
                        is not None
                        else None
                    ),
                    "network_seq": (
                        int(seq)
                        if seq
                        is not None
                        else None
                    ),
                }
            )
        return {
            "aid_id": str(
                row["aid_id"]
            ),
            "producer_id": str(
                row["producer_id"]
            ),
            "zid": (
                str(row["zid"])
                if row["zid"]
                is not None
                else None
            ),
            "program": str(
                row["program"]
            ),
            "item": str(row["item"]),
            "quantity": float(
                row["quantity"]
            ),
            "status": str(
                row["status"]
            ),
            "eligibility": (
                str(
                    row["eligibility"]
                )
                if row["eligibility"]
                is not None
                else None
            ),
            "events": event_list,
        }

    def list_aid(
        self,
        *,
        producer_id: str | None = None,
        status: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        sql = (
            "SELECT aid_id FROM"
            " agro_aid_requests"
            " WHERE 1=1"
        )
        params: list[object] = []
        if producer_id is not None:
            sql += (
                " AND producer_id = ?"
            )
            params.append(
                producer_id
            )
        if status is not None:
            sql += " AND status = ?"
            params.append(status)
        sql += (
            " ORDER BY created_at,"
            " rowid"
        )
        rows = self._db.query_all(
            sql, tuple(params)
        )
        return tuple(
            self.get_aid(
                str(r["aid_id"])
            )
            for r in rows
        )

    def aid_summary(
        self,
    ) -> dict[str, object]:
        total = self._db.query_one(
            "SELECT COUNT(*) AS n"
            " FROM"
            " agro_aid_requests"
        )
        by_status_rows = (
            self._db.query_all(
                "SELECT status,"
                " COUNT(*) AS n FROM"
                " agro_aid_requests"
                " GROUP BY status"
            )
        )
        by_program_rows = (
            self._db.query_all(
                "SELECT program,"
                " COUNT(*) AS n,"
                " SUM(quantity) AS q"
                " FROM"
                " agro_aid_requests"
                " GROUP BY program"
            )
        )
        by_status = {
            str(r["status"]): int(
                r["n"]
            )
            for r in by_status_rows
        }
        by_program = {}
        for r in by_program_rows:
            by_program[
                str(r["program"])
            ] = {
                "requests": int(
                    r["n"]
                ),
                "quantity": float(
                    r["q"] or 0
                ),
            }
        return {
            "aid_total": int(
                total["n"]
            )
            if total is not None
            else 0,
            "aid_by_status": (
                by_status
            ),
            "aid_by_program": (
                by_program
            ),
        }

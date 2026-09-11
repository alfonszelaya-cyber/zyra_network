"""SUBASTAS persistent store (marketplace)."""
from __future__ import annotations

import threading
import time
import uuid


def new_listing_id() -> str:
    return "LST-" + uuid.uuid4().hex[:10]


def new_bid_id() -> str:
    return "BID-" + uuid.uuid4().hex[:10]


class SubastasStore:
    def __init__(self, db, clock) -> None:
        self._db = db
        self._clock = clock
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._run(
            "CREATE TABLE IF NOT EXISTS"
            " sbs_accounts ("
            " account_id TEXT PRIMARY KEY,"
            " zid TEXT,"
            " name TEXT NOT NULL,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS"
            " sbs_listings ("
            " listing_id TEXT PRIMARY KEY,"
            " seller_account TEXT NOT NULL,"
            " seller_zid TEXT,"
            " title TEXT NOT NULL,"
            " description TEXT NOT NULL,"
            " base_price REAL NOT NULL,"
            " document_id TEXT,"
            " status TEXT NOT NULL,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS"
            " sbs_bids ("
            " bid_id TEXT PRIMARY KEY,"
            " listing_id TEXT NOT NULL,"
            " bidder_account TEXT NOT NULL,"
            " amount REAL NOT NULL,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS"
            " sbs_reputations ("
            " subject_zid TEXT NOT NULL,"
            " actor_zid TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " evidence TEXT NOT NULL,"
            " source TEXT NOT NULL,"
            " created_at TEXT NOT NULL)"
        )

    def _run(
        self,
        sql: str,
        params: tuple = (),
    ) -> None:
        if not params:
            self._db.execute(sql)
            return
        try:
            self._db.execute(sql, params)
            return
        except TypeError:
            self._db.execute(
                self._inline(sql, params)
            )

    @staticmethod
    def _inline(
        sql: str, params: tuple,
    ) -> str:
        parts = sql.split("?")
        if len(parts) != len(params) + 1:
            return sql
        assembled = parts[0]
        for index, value in enumerate(
            params
        ):
            assembled += (
                SubastasStore._literal(
                    value
                )
            )
            assembled += parts[index + 1]
        return assembled

    @staticmethod
    def _literal(value) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(
            value, (int, float)
        ):
            return repr(value)
        text = str(value).replace(
            "'", "''"
        )
        return "'" + text + "'"

    def _rows(self, sql: str) -> list:
        for name in (
            "query",
            "fetchall",
            "fetch_all",
            "fetch",
            "select",
        ):
            fn = getattr(
                self._db, name, None
            )
            if not callable(fn):
                continue
            try:
                rows = fn(sql)
                if rows is None:
                    continue
                return list(rows)
            except Exception:
                continue
        try:
            cursor = self._db.execute(sql)
        except Exception:
            return []
        if cursor is None:
            return []
        try:
            return list(
                cursor.fetchall()
            )
        except Exception:
            return []

    @staticmethod
    def _field(row, key: str, index: int):
        if isinstance(row, dict):
            return row.get(key)
        try:
            return row[index]
        except Exception:
            return None

    @staticmethod
    def _now() -> str:
        return time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        )

    def add_account(
        self,
        *,
        account_id: str,
        zid: str | None,
        name: str,
    ) -> dict:
        self._run(
            "INSERT INTO sbs_accounts ("
            " account_id, zid, name,"
            " created_at"
            ") VALUES (?, ?, ?, ?)",
            (
                account_id,
                zid,
                name,
                self._now(),
            ),
        )
        return {
            "account_id": account_id,
            "zid": zid,
            "name": name,
        }

    def get_account(
        self, account_id: str,
    ) -> dict | None:
        rows = self._rows(
            "SELECT account_id, zid,"
            " name FROM sbs_accounts"
            " WHERE account_id = "
            + self._literal(account_id)
        )
        if not rows:
            return None
        return {
            "account_id": (
                self._field(
                    rows[0], "a", 0
                )
            ),
            "zid": self._field(
                rows[0], "z", 1
            ),
            "name": self._field(
                rows[0], "n", 2
            ),
        }

    def add_listing(
        self,
        *,
        listing_id: str,
        seller_account: str,
        seller_zid: str | None,
        title: str,
        description: str,
        base_price: float,
        document_id: str | None,
    ) -> dict:
        self._run(
            "INSERT INTO sbs_listings ("
            " listing_id,"
            " seller_account,"
            " seller_zid, title,"
            " description, base_price,"
            " document_id, status,"
            " created_at"
            ") VALUES ("
            "?, ?, ?, ?, ?, ?,"
            " ?, 'open', ?)",
            (
                listing_id,
                seller_account,
                seller_zid,
                title,
                description,
                float(base_price),
                document_id,
                self._now(),
            ),
        )
        return {
            "listing_id": listing_id,
            "status": "open",
        }

    def list_open(self) -> list[dict]:
        rows = self._rows(
            "SELECT listing_id,"
            " seller_account,"
            " seller_zid, title,"
            " description, base_price,"
            " document_id, status,"
            " created_at"
            " FROM sbs_listings"
            " WHERE status = 'open'"
            " ORDER BY created_at ASC"
        )
        result: list[dict] = []
        for row in rows:
            result.append(
                {
                    "listing_id": (
                        self._field(
                            row,
                            "a",
                            0,
                        )
                    ),
                    "seller_account": (
                        self._field(
                            row,
                            "b",
                            1,
                        )
                    ),
                    "seller_zid": (
                        self._field(
                            row,
                            "c",
                            2,
                        )
                    ),
                    "title": (
                        self._field(
                            row,
                            "d",
                            3,
                        )
                    ),
                    "description": (
                        self._field(
                            row,
                            "e",
                            4,
                        )
                    ),
                    "base_price": (
                        self._field(
                            row,
                            "f",
                            5,
                        )
                    ),
                    "document_id": (
                        self._field(
                            row,
                            "g",
                            6,
                        )
                    ),
                    "status": (
                        self._field(
                            row,
                            "h",
                            7,
                        )
                    ),
                }
            )
        return result

    def _listing_row(
        self, listing_id: str,
    ):
        rows = self._rows(
            "SELECT seller_account,"
            " status, base_price"
            " FROM sbs_listings"
            " WHERE listing_id = "
            + self._literal(listing_id)
        )
        if not rows:
            return None
        return rows[0]

    def _highest_bid(
        self, listing_id: str,
    ):
        rows = self._rows(
            "SELECT bidder_account,"
            " amount FROM sbs_bids"
            " WHERE listing_id = "
            + self._literal(listing_id)
            + " ORDER BY amount DESC"
            + " LIMIT 1"
        )
        if not rows:
            return None
        return rows[0]

    def place_bid(
        self,
        *,
        bid_id: str,
        listing_id: str,
        bidder_account: str,
        amount: float,
    ) -> dict:
        with self._lock:
            row = self._listing_row(
                listing_id
            )
            if row is None:
                raise LookupError(
                    "listing not found:"
                    " " + listing_id
                )
            seller = str(
                self._field(
                    row, "s", 0
                )
            )
            status = str(
                self._field(
                    row, "t", 1
                )
            )
            base = float(
                self._field(
                    row, "b", 2
                )
                or 0
            )
            if status != "open":
                raise ValueError(
                    "listing is not open"
                )
            if (
                bidder_account
                == seller
            ):
                raise ValueError(
                    "seller cannot bid"
                    " own listing"
                )
            amt = float(amount)
            if amt <= base:
                raise ValueError(
                    "bid must exceed"
                    " base price"
                )
            top = self._highest_bid(
                listing_id
            )
            if top is not None:
                best = float(
                    self._field(
                        top,
                        "m",
                        1,
                    )
                    or 0
                )
                if amt <= best:
                    raise ValueError(
                        "bid must exceed"
                        " current highest"
                    )
            self._run(
                "INSERT INTO sbs_bids ("
                " bid_id, listing_id,"
                " bidder_account,"
                " amount, created_at"
                ") VALUES ("
                "?, ?, ?, ?, ?)",
                (
                    bid_id,
                    listing_id,
                    bidder_account,
                    amt,
                    self._now(),
                ),
            )
            return {
                "bid_id": bid_id,
                "listing_id": (
                    listing_id
                ),
                "bidder_account": (
                    bidder_account
                ),
                "amount": amt,
            }

    def close_listing(
        self,
        *,
        listing_id: str,
        seller_account: str,
    ) -> dict:
        with self._lock:
            row = self._listing_row(
                listing_id
            )
            if row is None:
                raise LookupError(
                    "listing not found:"
                    " " + listing_id
                )
            seller = str(
                self._field(
                    row, "s", 0
                )
            )
            status = str(
                self._field(
                    row, "t", 1
                )
            )
            if seller != seller_account:
                raise PermissionError(
                    "only the seller"
                    " can close"
                )
            if status != "open":
                raise ValueError(
                    "already closed"
                )
            top = self._highest_bid(
                listing_id
            )
            if top is None:
                raise ValueError(
                    "no bids"
                )
            winner = str(
                self._field(
                    top, "w", 0
                )
            )
            price = float(
                self._field(
                    top, "p", 1
                )
            )
            self._run(
                "UPDATE sbs_listings"
                " SET status = 'closed'"
                " WHERE listing_id = "
                + self._literal(
                    listing_id
                )
            )
            return {
                "listing_id": (
                    listing_id
                ),
                "winner_account": (
                    winner
                ),
                "final_price": price,
            }

    def record_reputation(
        self,
        *,
        subject_zid: str,
        actor_zid: str,
        kind: str,
        evidence: str,
        source: str,
    ) -> dict:
        self._run(
            "INSERT INTO"
            " sbs_reputations ("
            " subject_zid, actor_zid,"
            " kind, evidence, source,"
            " created_at"
            ") VALUES ("
            "?, ?, ?, ?, ?, ?)",
            (
                subject_zid,
                actor_zid,
                kind,
                evidence,
                source,
                self._now(),
            ),
        )
        return {"recorded": True}

    def summary(self) -> dict:
        open_count = len(
            self.list_open()
        )
        accounts = self._rows(
            "SELECT COUNT(*) FROM"
            " sbs_accounts"
        )
        bids = self._rows(
            "SELECT COUNT(*) FROM"
            " sbs_bids"
        )
        total = (
            open_count
            + len(
                self._closed_ids()
            )
        )
        return {
            "listings_total": total,
            "open_listings": (
                open_count
            ),
            "accounts": int(
                self._field(
                    accounts[0],
                    "c",
                    0,
                )
                or 0
            )
            if accounts
            else 0,
            "bids": int(
                self._field(
                    bids[0], "c", 0
                )
                or 0
            )
            if bids
            else 0,
        }

    def _closed_ids(self) -> list:
        return self._rows(
            "SELECT listing_id"
            " FROM sbs_listings"
            " WHERE status = 'closed'"
        )

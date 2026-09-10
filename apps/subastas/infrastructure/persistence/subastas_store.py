"""SUBASTAS durable store."""
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
        "subastas",
        (
            "CREATE TABLE sbs_accounts ("
            " account_id TEXT PRIMARY KEY,"
            " zid TEXT,"
            " name TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE sbs_listings ("
            " listing_id TEXT PRIMARY KEY,"
            " seller_account TEXT NOT NULL,"
            " seller_zid TEXT,"
            " title TEXT NOT NULL,"
            " description TEXT NOT NULL,"
            " base_price REAL NOT NULL,"
            " document_id TEXT,"
            " status TEXT NOT NULL"
            " DEFAULT 'open',"
            " winner_account TEXT,"
            " final_price REAL,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE sbs_bids ("
            " bid_id TEXT PRIMARY KEY,"
            " listing_id TEXT NOT NULL,"
            " bidder_account TEXT NOT NULL,"
            " amount REAL NOT NULL,"
            " created_at REAL NOT NULL)",
        ),
    ),
)


class SubastasStore:
    def __init__(
        self, db: Database, clock
    ) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db, "subastas", _MIGRATIONS
        ).run(clock)

    def add_account(
        self,
        *,
        account_id: str,
        zid: str | None,
        name: str,
    ) -> dict[str, object]:
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sbs_accounts"
                " (account_id, zid, name,"
                "  created_at)"
                " VALUES (?, ?, ?, ?)",
                (
                    account_id,
                    zid,
                    name,
                    now,
                ),
            )
        return self.get_account(account_id)

    def get_account(
        self, account_id: str
    ) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM sbs_accounts"
            " WHERE account_id = ?",
            (account_id,),
        )
        if row is None:
            raise LookupError(
                "unknown account:"
                f" {account_id}"
            )
        zid = row["zid"]
        return {
            "account_id": str(
                row["account_id"]
            ),
            "zid": (
                str(zid)
                if zid is not None
                else None
            ),
            "name": str(row["name"]),
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
    ) -> dict[str, object]:
        if base_price <= 0:
            raise ValueError(
                "base_price must be"
                " positive"
            )
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sbs_listings"
                " (listing_id,"
                "  seller_account,"
                "  seller_zid, title,"
                "  description, base_price,"
                "  document_id, status,"
                "  created_at)"
                " VALUES (?, ?, ?, ?, ?, ?,"
                "  ?, 'open', ?)",
                (
                    listing_id,
                    seller_account,
                    seller_zid,
                    title,
                    description,
                    base_price,
                    document_id,
                    now,
                ),
            )
        return self.get_listing(listing_id)

    def get_listing(
        self, listing_id: str
    ) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM sbs_listings"
            " WHERE listing_id = ?",
            (listing_id,),
        )
        if row is None:
            raise LookupError(
                "unknown listing:"
                f" {listing_id}"
            )
        doc = row["document_id"]
        winner = row["winner_account"]
        return {
            "listing_id": str(
                row["listing_id"]
            ),
            "seller_account": str(
                row["seller_account"]
            ),
            "seller_zid": (
                str(row["seller_zid"])
                if row["seller_zid"]
                is not None
                else None
            ),
            "title": str(row["title"]),
            "description": str(
                row["description"]
            ),
            "base_price": float(
                row["base_price"]
            ),
            "document_id": (
                str(doc)
                if doc is not None
                else None
            ),
            "status": str(row["status"]),
            "winner_account": (
                str(winner)
                if winner is not None
                else None
            ),
            "final_price": (
                float(row["final_price"])
                if row["final_price"]
                is not None
                else None
            ),
        }

    def list_open(self) -> tuple[
        dict[str, object], ...
    ]:
        rows = self._db.query_all(
            "SELECT listing_id FROM"
            " sbs_listings WHERE"
            " status = 'open'"
            " ORDER BY created_at DESC"
        )
        return tuple(
            self.get_listing(
                str(r["listing_id"])
            )
            for r in rows
        )

    def place_bid(
        self,
        *,
        bid_id: str,
        listing_id: str,
        bidder_account: str,
        amount: float,
    ) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM sbs_listings"
            " WHERE listing_id = ?"
            " AND status = 'open'",
            (listing_id,),
        )
        if row is None:
            raise LookupError(
                "listing not open:"
                f" {listing_id}"
            )
        seller = str(row["seller_account"])
        if seller == bidder_account:
            raise ValueError(
                "seller cannot bid on"
                " own listing"
            )
        top = self._db.query_one(
            "SELECT amount FROM sbs_bids"
            " WHERE listing_id = ?"
            " ORDER BY amount DESC"
            " LIMIT 1",
            (listing_id,),
        )
        minimum = float(
            row["base_price"]
        )
        if top is not None:
            minimum = float(top["amount"])
        if amount <= minimum:
            raise ValueError(
                "bid must exceed"
                f" {minimum}"
            )
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sbs_bids"
                " (bid_id, listing_id,"
                "  bidder_account, amount,"
                "  created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    bid_id,
                    listing_id,
                    bidder_account,
                    amount,
                    now,
                ),
            )
        return {
            "bid_id": bid_id,
            "listing_id": listing_id,
            "amount": amount,
        }

    def close_listing(
        self,
        *,
        listing_id: str,
        seller_account: str,
    ) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM sbs_listings"
            " WHERE listing_id = ?"
            " AND status = 'open'",
            (listing_id,),
        )
        if row is None:
            raise LookupError(
                "listing not open:"
                f" {listing_id}"
            )
        if str(row["seller_account"]) != (
            seller_account
        ):
            raise ValueError(
                "only the seller can"
                " close the listing"
            )
        top = self._db.query_one(
            "SELECT bidder_account, amount"
            " FROM sbs_bids WHERE"
            " listing_id = ?"
            " ORDER BY amount DESC"
            " LIMIT 1",
            (listing_id,),
        )
        winner = (
            str(top["bidder_account"])
            if top is not None
            else None
        )
        final = (
            float(top["amount"])
            if top is not None
            else float(row["base_price"])
        )
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE sbs_listings SET"
                " status = 'sold',"
                " winner_account = ?,"
                " final_price = ?"
                " WHERE listing_id = ?",
                (
                    winner,
                    final,
                    listing_id,
                ),
            )
        return self.get_listing(listing_id)

    def bids_for(
        self, *, listing_id: str
    ) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM sbs_bids"
            " WHERE listing_id = ?"
            " ORDER BY amount DESC",
            (listing_id,),
        )
        return tuple(
            {
                "bid_id": str(
                    r["bid_id"]
                ),
                "bidder_account": str(
                    r["bidder_account"]
                ),
                "amount": float(
                    r["amount"]
                ),
            }
            for r in rows
        )

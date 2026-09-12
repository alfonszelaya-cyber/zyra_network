"""SUBASTAS commerce layer - ADD-ONLY module."""
from __future__ import annotations

import threading
import time
import uuid

PLATFORM_FEE_RATE = 0.05


def _nid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:10]


class CommerceStore:
    """ADD-ONLY commerce layer over the existing
    SUBASTAS database."""

    def __init__(self, db, clock) -> None:
        self._db = db
        self._clock = clock
        self._lock = threading.Lock()
        self._ensure_schema()

    def _now(self) -> float:
        try:
            return float(self._clock.now())
        except Exception:
            return time.time()

    def _ensure_schema(self) -> None:
        for ddl in (
            "ALTER TABLE sbs_listings ADD COLUMN winner_account TEXT",
            "ALTER TABLE sbs_listings ADD COLUMN final_price REAL",
            "ALTER TABLE sbs_listings ADD COLUMN closed_at REAL",
        ):
            try:
                self._db.execute(ddl)
            except Exception:
                pass
        for ddl in (
            "CREATE TABLE IF NOT EXISTS sbs_orders ("
            " order_id TEXT PRIMARY KEY,"
            " listing_id TEXT NOT NULL,"
            " buyer_account TEXT NOT NULL,"
            " buyer_zid TEXT,"
            " seller_account TEXT NOT NULL,"
            " seller_zid TEXT,"
            " source TEXT NOT NULL,"
            " subtotal REAL NOT NULL,"
            " platform_fee REAL NOT NULL,"
            " total REAL NOT NULL,"
            " currency TEXT NOT NULL DEFAULT 'USD',"
            " status TEXT NOT NULL,"
            " created_at REAL NOT NULL,"
            " updated_at REAL NOT NULL)",
            "CREATE TABLE IF NOT EXISTS sbs_payments ("
            " payment_id TEXT PRIMARY KEY,"
            " order_id TEXT NOT NULL,"
            " provider TEXT NOT NULL,"
            " amount REAL NOT NULL,"
            " currency TEXT NOT NULL DEFAULT 'USD',"
            " status TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE IF NOT EXISTS sbs_commissions ("
            " commission_id TEXT PRIMARY KEY,"
            " order_id TEXT NOT NULL,"
            " rate REAL NOT NULL,"
            " gross_amount REAL NOT NULL,"
            " commission_amount REAL NOT NULL,"
            " currency TEXT NOT NULL DEFAULT 'USD',"
            " created_at REAL NOT NULL)",
            "CREATE TABLE IF NOT EXISTS sbs_settlements ("
            " settlement_id TEXT PRIMARY KEY,"
            " order_id TEXT NOT NULL,"
            " seller_account TEXT NOT NULL,"
            " gross_amount REAL NOT NULL,"
            " commission REAL NOT NULL,"
            " net_amount REAL NOT NULL,"
            " currency TEXT NOT NULL DEFAULT 'USD',"
            " status TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE IF NOT EXISTS sbs_shipments ("
            " shipment_id TEXT PRIMARY KEY,"
            " order_id TEXT NOT NULL,"
            " carrier TEXT NOT NULL,"
            " origin TEXT NOT NULL,"
            " destination TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at REAL NOT NULL,"
            " updated_at REAL NOT NULL)",
            "CREATE TABLE IF NOT EXISTS sbs_tracking_events ("
            " event_id TEXT PRIMARY KEY,"
            " shipment_id TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " location TEXT,"
            " description TEXT,"
            " occurred_at REAL NOT NULL)",
            "CREATE TABLE IF NOT EXISTS sbs_reputation_events ("
            " event_id TEXT PRIMARY KEY,"
            " order_id TEXT,"
            " subject_zid TEXT NOT NULL,"
            " actor_zid TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " evidence TEXT NOT NULL,"
            " network_recorded INTEGER NOT NULL DEFAULT 0,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE IF NOT EXISTS sbs_opportunities ("
            " opportunity_id TEXT PRIMARY KEY,"
            " title TEXT NOT NULL,"
            " category TEXT,"
            " purchase_price REAL NOT NULL,"
            " shipping_cost REAL NOT NULL,"
            " fees REAL NOT NULL,"
            " estimated_sale_price REAL NOT NULL,"
            " total_cost REAL NOT NULL,"
            " expected_profit REAL NOT NULL,"
            " margin_percent REAL NOT NULL,"
            " demand_score REAL NOT NULL,"
            " risk_score REAL NOT NULL,"
            " opportunity_score REAL NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
        ):
            self._db.execute(ddl)

    def _run(self, sql, params=()) -> None:
        if not params:
            self._db.execute(sql)
            return
        try:
            self._db.execute(sql, params)
            return
        except TypeError:
            self._db.execute(self._inline(sql, params))

    @staticmethod
    def _inline(sql, params) -> str:
        parts = sql.split("?")
        if len(parts) != len(params) + 1:
            return sql
        assembled = parts[0]
        for index, value in enumerate(params):
            assembled += CommerceStore._literal(value)
            assembled += parts[index + 1]
        return assembled

    @staticmethod
    def _literal(value) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return repr(value)
        text = str(value).replace("'", "''")
        return "'" + text + "'"

    def _rows(self, sql) -> list:
        for name in ("query", "fetchall", "fetch_all", "fetch", "select"):
            fn = getattr(self._db, name, None)
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
            return list(cursor.fetchall())
        except Exception:
            return []

    @staticmethod
    def _field(row, key, index):
        if isinstance(row, dict):
            return row.get(key)
        try:
            return row[index]
        except Exception:
            return None

    def persist_winner(self, *, listing_id: str) -> dict:
        with self._lock:
            rows = self._rows(
                "SELECT bidder_account, amount FROM sbs_bids"
                " WHERE listing_id = "
                + self._literal(listing_id)
                + " ORDER BY amount DESC LIMIT 1"
            )
            if not rows:
                raise LookupError("no bids for: " + listing_id)
            winner = str(self._field(rows[0], "w", 0))
            price = float(self._field(rows[0], "p", 1))
            now = self._now()
            self._run(
                "UPDATE sbs_listings SET"
                " winner_account = "
                + self._literal(winner)
                + ", final_price = "
                + self._literal(price)
                + ", closed_at = "
                + self._literal(now)
                + " WHERE listing_id = "
                + self._literal(listing_id)
            )
            return {
                "listing_id": listing_id,
                "winner_account": winner,
                "final_price": price,
            }

    def get_listing_full(self, listing_id: str):
        rows = self._rows(
            "SELECT listing_id, seller_account, seller_zid,"
            " title, base_price, document_id, status,"
            " winner_account, final_price, closed_at"
            " FROM sbs_listings WHERE listing_id = "
            + self._literal(listing_id)
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "listing_id": self._field(row, "a", 0),
            "seller_account": self._field(row, "b", 1),
            "seller_zid": self._field(row, "c", 2),
            "title": self._field(row, "d", 3),
            "base_price": self._field(row, "e", 4),
            "document_id": self._field(row, "f", 5),
            "status": self._field(row, "g", 6),
            "winner_account": self._field(row, "h", 7),
            "final_price": self._field(row, "i", 8),
            "closed_at": self._field(row, "j", 9),
        }

    def account_zid(self, account_id: str):
        rows = self._rows(
            "SELECT zid FROM sbs_accounts WHERE account_id = "
            + self._literal(account_id)
        )
        if not rows:
            return None
        zid = self._field(rows[0], "z", 0)
        return str(zid) if zid is not None else None

    def create_order(
        self, *, order_id, listing_id, buyer_account, source,
    ) -> dict:
        with self._lock:
            listing = self.get_listing_full(listing_id)
            if listing is None:
                raise LookupError("listing not found: " + listing_id)
            if source == "auction":
                if listing["status"] != "closed":
                    raise ValueError("auction not closed yet")
                if listing["winner_account"] != buyer_account:
                    raise ValueError("buyer is not the auction winner")
                subtotal = float(listing["final_price"] or 0)
            else:
                if listing["status"] != "open":
                    raise ValueError("listing is not open")
                subtotal = float(listing["base_price"])
            dup = self._rows(
                "SELECT order_id FROM sbs_orders WHERE listing_id = "
                + self._literal(listing_id)
            )
            if dup:
                raise ValueError("order already exists for this listing")
            fee = round(subtotal * PLATFORM_FEE_RATE, 2)
            now = self._now()
            self._run(
                "INSERT INTO sbs_orders ("
                " order_id, listing_id, buyer_account, buyer_zid,"
                " seller_account, seller_zid, source, subtotal,"
                " platform_fee, total, currency, status,"
                " created_at, updated_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
                " 'USD', 'created', ?, ?)",
                (
                    order_id,
                    listing_id,
                    buyer_account,
                    self.account_zid(buyer_account),
                    listing["seller_account"],
                    listing["seller_zid"],
                    source,
                    subtotal,
                    fee,
                    subtotal,
                    now,
                    now,
                ),
            )
            return self.get_order(order_id)

    def get_order(self, order_id: str) -> dict:
        rows = self._rows(
            "SELECT order_id, listing_id, buyer_account,"
            " buyer_zid, seller_account, seller_zid, source,"
            " subtotal, platform_fee, total, currency, status,"
            " created_at, updated_at FROM sbs_orders"
            " WHERE order_id = "
            + self._literal(order_id)
        )
        if not rows:
            raise LookupError("order not found: " + order_id)
        row = rows[0]
        order = {
            "order_id": self._field(row, "a", 0),
            "listing_id": self._field(row, "b", 1),
            "buyer_account": self._field(row, "c", 2),
            "buyer_zid": self._field(row, "d", 3),
            "seller_account": self._field(row, "e", 4),
            "seller_zid": self._field(row, "f", 5),
            "source": self._field(row, "g", 6),
            "subtotal": self._field(row, "h", 7),
            "platform_fee": self._field(row, "i", 8),
            "total": self._field(row, "j", 9),
            "currency": self._field(row, "k", 10),
            "status": self._field(row, "l", 11),
            "payments": [],
            "commission": None,
            "settlement": None,
            "shipment": None,
        }
        pays = self._rows(
            "SELECT payment_id, provider, amount, status"
            " FROM sbs_payments WHERE order_id = "
            + self._literal(order_id)
        )
        for p in pays:
            order["payments"].append(
                {
                    "payment_id": self._field(p, "a", 0),
                    "provider": self._field(p, "b", 1),
                    "amount": self._field(p, "c", 2),
                    "status": self._field(p, "d", 3),
                }
            )
        com = self._rows(
            "SELECT commission_id, rate, commission_amount"
            " FROM sbs_commissions WHERE order_id = "
            + self._literal(order_id)
        )
        if com:
            order["commission"] = {
                "commission_id": self._field(com[0], "a", 0),
                "rate": self._field(com[0], "b", 1),
                "commission_amount": self._field(com[0], "c", 2),
            }
        stl = self._rows(
            "SELECT settlement_id, gross_amount, commission,"
            " net_amount, status FROM sbs_settlements"
            " WHERE order_id = "
            + self._literal(order_id)
        )
        if stl:
            order["settlement"] = {
                "settlement_id": self._field(stl[0], "a", 0),
                "gross_amount": self._field(stl[0], "b", 1),
                "commission": self._field(stl[0], "c", 2),
                "net_amount": self._field(stl[0], "d", 3),
                "status": self._field(stl[0], "e", 4),
            }
        shp = self._rows(
            "SELECT shipment_id, carrier, origin, destination,"
            " status FROM sbs_shipments WHERE order_id = "
            + self._literal(order_id)
        )
        if shp:
            order["shipment"] = {
                "shipment_id": self._field(shp[0], "a", 0),
                "carrier": self._field(shp[0], "b", 1),
                "origin": self._field(shp[0], "c", 2),
                "destination": self._field(shp[0], "d", 3),
                "status": self._field(shp[0], "e", 4),
            }
        return order

    def pay_order(self, *, order_id, provider) -> dict:
        with self._lock:
            order = self.get_order(order_id)
            if order["status"] != "created":
                raise ValueError("order is not payable")
            now = self._now()
            self._run(
                "INSERT INTO sbs_payments ("
                " payment_id, order_id, provider, amount,"
                " currency, status, created_at"
                ") VALUES (?, ?, ?, ?, 'USD', 'captured', ?)",
                (_nid("PAY-"), order_id, provider, order["total"], now),
            )
            self._run(
                "INSERT INTO sbs_commissions ("
                " commission_id, order_id, rate, gross_amount,"
                " commission_amount, currency, created_at"
                ") VALUES (?, ?, ?, ?, ?, 'USD', ?)",
                (
                    _nid("COM-"),
                    order_id,
                    PLATFORM_FEE_RATE,
                    order["total"],
                    order["platform_fee"],
                    now,
                ),
            )
            self._run(
                "UPDATE sbs_orders SET status = 'paid', updated_at = "
                + self._literal(now)
                + " WHERE order_id = "
                + self._literal(order_id)
            )
            return self.get_order(order_id)

    def settle_order(self, *, order_id) -> dict:
        with self._lock:
            order = self.get_order(order_id)
            if order["status"] != "paid":
                raise ValueError("order is not settleable")
            net = round(order["total"] - order["platform_fee"], 2)
            self._run(
                "INSERT INTO sbs_settlements ("
                " settlement_id, order_id, seller_account,"
                " gross_amount, commission, net_amount,"
                " currency, status, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, 'USD', 'settled', ?)",
                (
                    _nid("SET-"),
                    order_id,
                    order["seller_account"],
                    order["total"],
                    order["platform_fee"],
                    net,
                    self._now(),
                ),
            )
            self._run(
                "UPDATE sbs_orders SET status = 'settled',"
                " updated_at = "
                + self._literal(self._now())
                + " WHERE order_id = "
                + self._literal(order_id)
            )
            return self.get_order(order_id)

    def create_shipment(
        self, *, shipment_id, order_id, carrier, origin, destination,
    ) -> dict:
        with self._lock:
            order = self.get_order(order_id)
            if order["status"] != "settled":
                raise ValueError("order is not shippable")
            now = self._now()
            self._run(
                "INSERT INTO sbs_shipments ("
                " shipment_id, order_id, carrier, origin,"
                " destination, status, created_at, updated_at"
                ") VALUES (?, ?, ?, ?, ?, 'created', ?, ?)",
                (shipment_id, order_id, carrier, origin, destination, now, now),
            )
            self._run(
                "UPDATE sbs_orders SET status = 'shipped', updated_at = "
                + self._literal(now)
                + " WHERE order_id = "
                + self._literal(order_id)
            )
            return self.get_shipment(shipment_id)

    def get_shipment(self, shipment_id: str) -> dict:
        rows = self._rows(
            "SELECT shipment_id, order_id, carrier, origin,"
            " destination, status FROM sbs_shipments"
            " WHERE shipment_id = "
            + self._literal(shipment_id)
        )
        if not rows:
            raise LookupError("shipment not found: " + shipment_id)
        row = rows[0]
        events = self._rows(
            "SELECT event_id, status, location, description"
            " FROM sbs_tracking_events WHERE shipment_id = "
            + self._literal(shipment_id)
            + " ORDER BY occurred_at"
        )
        tracking = []
        for e in events:
            tracking.append(
                {
                    "event_id": self._field(e, "a", 0),
                    "status": self._field(e, "b", 1),
                    "location": self._field(e, "c", 2),
                    "description": self._field(e, "d", 3),
                }
            )
        return {
            "shipment_id": self._field(row, "a", 0),
            "order_id": self._field(row, "b", 1),
            "carrier": self._field(row, "c", 2),
            "origin": self._field(row, "d", 3),
            "destination": self._field(row, "e", 4),
            "status": self._field(row, "f", 5),
            "tracking": tracking,
        }

    def add_tracking(
        self, *, shipment_id, status, location, description,
    ) -> dict:
        with self._lock:
            current = self.get_shipment(shipment_id)
            if current["status"] == "delivered":
                raise ValueError("shipment already delivered")
            self._run(
                "INSERT INTO sbs_tracking_events ("
                " event_id, shipment_id, status, location,"
                " description, occurred_at"
                ") VALUES (?, ?, ?, ?, ?, ?)",
                (_nid("TRK-"), shipment_id, status, location, description, self._now()),
            )
            self._run(
                "UPDATE sbs_shipments SET status = "
                + self._literal(status)
                + ", updated_at = "
                + self._literal(self._now())
                + " WHERE shipment_id = "
                + self._literal(shipment_id)
            )
            return self.get_shipment(shipment_id)

    def confirm_delivery(self, *, shipment_id) -> dict:
        with self._lock:
            current = self.get_shipment(shipment_id)
            if current["status"] == "delivered":
                raise ValueError("shipment already delivered")
            now = self._now()
            self._run(
                "INSERT INTO sbs_tracking_events ("
                " event_id, shipment_id, status, location,"
                " description, occurred_at"
                ") VALUES (?, ?, 'delivered', NULL,"
                " 'entregado al comprador', ?)",
                (_nid("TRK-"), shipment_id, now),
            )
            self._run(
                "UPDATE sbs_shipments SET status = 'delivered',"
                " updated_at = "
                + self._literal(now)
                + " WHERE shipment_id = "
                + self._literal(shipment_id)
            )
            self._run(
                "UPDATE sbs_orders SET status = 'delivered',"
                " updated_at = "
                + self._literal(now)
                + " WHERE order_id = "
                + self._literal(current["order_id"])
            )
            return self.get_shipment(shipment_id)

    def record_rep_event(
        self, *, order_id, subject_zid, actor_zid, kind, evidence,
        network_recorded,
    ) -> dict:
        self._run(
            "INSERT INTO sbs_reputation_events ("
            " event_id, order_id, subject_zid, actor_zid,"
            " kind, evidence, network_recorded, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _nid("REP-"),
                order_id,
                subject_zid,
                actor_zid,
                kind,
                evidence,
                1 if network_recorded else 0,
                self._now(),
            ),
        )
        return {"recorded": True}

    def create_opportunity(
        self, *, opportunity_id, title, category, purchase_price,
        shipping_cost, fees, estimated_sale_price, demand_score,
        risk_score,
    ) -> dict:
        total_cost = round(purchase_price + shipping_cost + fees, 2)
        if total_cost <= 0:
            raise ValueError("total cost must be positive")
        expected_profit = round(estimated_sale_price - total_cost, 2)
        margin_percent = round(expected_profit / total_cost * 100, 2)
        score = round(
            margin_percent * 0.5
            + demand_score * 30
            + (1 - risk_score) * 20,
            2,
        )
        self._run(
            "INSERT INTO sbs_opportunities ("
            " opportunity_id, title, category, purchase_price,"
            " shipping_cost, fees, estimated_sale_price,"
            " total_cost, expected_profit, margin_percent,"
            " demand_score, risk_score, opportunity_score,"
            " status, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)",
            (
                opportunity_id,
                title,
                category,
                purchase_price,
                shipping_cost,
                fees,
                estimated_sale_price,
                total_cost,
                expected_profit,
                margin_percent,
                demand_score,
                risk_score,
                score,
                self._now(),
            ),
        )
        return {
            "opportunity_id": opportunity_id,
            "title": title,
            "total_cost": total_cost,
            "expected_profit": expected_profit,
            "margin_percent": margin_percent,
            "opportunity_score": score,
        }

    def list_opportunities(self) -> list:
        rows = self._rows(
            "SELECT opportunity_id, title, category,"
            " purchase_price, estimated_sale_price, total_cost,"
            " expected_profit, margin_percent, opportunity_score,"
            " status FROM sbs_opportunities ORDER BY created_at"
        )
        result = []
        for row in rows:
            result.append(
                {
                    "opportunity_id": self._field(row, "a", 0),
                    "title": self._field(row, "b", 1),
                    "category": self._field(row, "c", 2),
                    "purchase_price": self._field(row, "d", 3),
                    "estimated_sale_price": self._field(row, "e", 4),
                    "total_cost": self._field(row, "f", 5),
                    "expected_profit": self._field(row, "g", 6),
                    "margin_percent": self._field(row, "h", 7),
                    "opportunity_score": self._field(row, "i", 8),
                    "status": self._field(row, "j", 9),
                }
            )
        return result

    def summary(self) -> dict:
        orders = self._rows("SELECT COUNT(*) FROM sbs_orders")
        delivered = self._rows(
            "SELECT COUNT(*) FROM sbs_orders WHERE status = 'delivered'"
        )
        opps = self._rows("SELECT COUNT(*) FROM sbs_opportunities")
        return {
            "orders_total": int(self._field(orders[0], "c", 0) or 0) if orders else 0,
            "orders_delivered": int(self._field(delivered[0], "c", 0) or 0) if delivered else 0,
            "opportunities": int(self._field(opps[0], "c", 0) or 0) if opps else 0,
        }

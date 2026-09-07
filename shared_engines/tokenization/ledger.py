"""Double-entry token ledger with capped emission and redemption.

Accounting model (bank-grade): every movement records ONE
transaction row (debit/credit accounts) and applies the
user balance in the same transaction. The treasury is the
MINT SOURCE: its row is documentary, it never carries or
checks a balance. Users' balances obey the machine-checked
invariant: sum(user balances) == minted - redeemed.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Final

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import (
    ConfigurationError,
    IntegrityError,
)
from shared_engines.common.identifiers import new_id
from shared_engines.common.validation import (
    require_int_range,
    require_non_empty_str,
)
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)
from shared_engines.tokenization.errors import (
    DuplicateRuleError,
    EmissionCapExceededError,
    InsufficientBalanceError,
    ItemInactiveError,
    RuleInactiveError,
    UnknownItemError,
    UnknownRuleError,
)

SYSTEM_TREASURY: Final[str] = "zyra://treasury"
SYSTEM_BURN: Final[str] = "zyra://burn"
_SECONDS_PER_DAY: Final[int] = 86_400

TOKEN_MIGRATIONS = (
    Migration(
        1,
        "token_accounts",
        (
            "CREATE TABLE token_accounts ("
            " account_id TEXT PRIMARY KEY,"
            " balance INTEGER NOT NULL DEFAULT 0,"
            " created_at REAL NOT NULL,"
            " updated_at REAL NOT NULL)",
        ),
    ),
    Migration(
        2,
        "token_transactions",
        (
            "CREATE TABLE token_transactions ("
            " tx_id TEXT PRIMARY KEY,"
            " kind TEXT NOT NULL,"
            " debit_account TEXT NOT NULL,"
            " credit_account TEXT NOT NULL,"
            " amount INTEGER NOT NULL,"
            " reason TEXT NOT NULL,"
            " ref_type TEXT NOT NULL,"
            " ref_id TEXT NOT NULL,"
            " actor TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE INDEX token_tx_account"
            " ON token_transactions (debit_account, created_at)",
            "CREATE INDEX token_tx_credit"
            " ON token_transactions (credit_account, created_at)",
        ),
    ),
    Migration(
        3,
        "emission_rules",
        (
            "CREATE TABLE emission_rules ("
            " rule_id TEXT PRIMARY KEY,"
            " activity TEXT NOT NULL UNIQUE,"
            " amount INTEGER NOT NULL,"
            " daily_cap INTEGER,"
            " lifetime_cap INTEGER,"
            " active INTEGER NOT NULL DEFAULT 1,"
            " created_at REAL NOT NULL)",
        ),
    ),
    Migration(
        4,
        "emission_log",
        (
            "CREATE TABLE emission_log ("
            " emission_id TEXT PRIMARY KEY,"
            " rule_id TEXT NOT NULL,"
            " subject_zid TEXT NOT NULL,"
            " day INTEGER NOT NULL,"
            " amount INTEGER NOT NULL,"
            " tx_id TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE INDEX emission_log_rule_subject"
            " ON emission_log (rule_id, subject_zid, day)",
        ),
    ),
    Migration(
        5,
        "redemption_items",
        (
            "CREATE TABLE redemption_items ("
            " item_id TEXT PRIMARY KEY,"
            " title TEXT NOT NULL,"
            " cost INTEGER NOT NULL,"
            " active INTEGER NOT NULL DEFAULT 1,"
            " created_at REAL NOT NULL)",
        ),
    ),
    Migration(
        6,
        "redemptions",
        (
            "CREATE TABLE redemptions ("
            " redemption_id TEXT PRIMARY KEY,"
            " subject_zid TEXT NOT NULL,"
            " item_id TEXT NOT NULL,"
            " cost INTEGER NOT NULL,"
            " tx_id TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE INDEX redemptions_subject"
            " ON redemptions (subject_zid, created_at)",
        ),
    ),
)


@dataclass(frozen=True)
class EmissionRule:
    rule_id: str
    activity: str
    amount: int
    daily_cap: int | None
    lifetime_cap: int | None
    active: bool
    created_at: float


@dataclass(frozen=True)
class RedemptionItem:
    item_id: str
    title: str
    cost: int
    active: bool
    created_at: float


@dataclass(frozen=True)
class LedgerTransaction:
    tx_id: str
    kind: str
    debit_account: str
    credit_account: str
    amount: int
    reason: str
    ref_type: str
    ref_id: str
    actor: str
    created_at: float


@dataclass(frozen=True)
class RedemptionRecord:
    redemption_id: str
    subject_zid: str
    item_id: str
    cost: int
    tx_id: str
    created_at: float


class TokenLedger:
    """The accounting core: accounts, transactions, rules."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db, "tokenization", TOKEN_MIGRATIONS
        ).run(clock)

    @staticmethod
    def _day_of(now: float) -> int:
        return int(now // _SECONDS_PER_DAY)

    def _ensure_account(
        self, cursor: sqlite3.Cursor, account: str, now: float
    ) -> None:
        cursor.execute(
            "INSERT OR IGNORE INTO token_accounts"
            " (account_id, balance, created_at, updated_at)"
            " VALUES (?, 0, ?, ?)",
            (account, now, now),
        )

    def _credit(
        self,
        cursor: sqlite3.Cursor,
        account: str,
        amount: int,
        now: float,
    ) -> None:
        self._ensure_account(cursor, account, now)
        cursor.execute(
            "UPDATE token_accounts SET balance = balance + ?,"
            " updated_at = ? WHERE account_id = ?",
            (amount, now, account),
        )

    def _debit(
        self,
        cursor: sqlite3.Cursor,
        account: str,
        amount: int,
        now: float,
    ) -> None:
        row = cursor.execute(
            "SELECT balance FROM token_accounts"
            " WHERE account_id = ?",
            (account,),
        ).fetchone()
        balance = int(row["balance"]) if row is not None else 0
        if balance < amount:
            raise InsufficientBalanceError(
                f"account {account} has {balance},"
                f" needs {amount}"
            )
        cursor.execute(
            "UPDATE token_accounts SET balance = balance - ?,"
            " updated_at = ? WHERE account_id = ?",
            (amount, now, account),
        )

    def _record_tx(
        self,
        cursor: sqlite3.Cursor,
        *,
        kind: str,
        debit: str,
        credit: str,
        amount: int,
        reason: str,
        ref_type: str,
        ref_id: str,
        actor: str,
        now: float,
    ) -> LedgerTransaction:
        tx_id = f"TX-{new_id()}"
        cursor.execute(
            "INSERT INTO token_transactions"
            " (tx_id, kind, debit_account, credit_account,"
            "  amount, reason, ref_type, ref_id, actor,"
            "  created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tx_id,
                kind,
                debit,
                credit,
                amount,
                reason,
                ref_type,
                ref_id,
                actor,
                now,
            ),
        )
        return LedgerTransaction(
            tx_id=tx_id,
            kind=kind,
            debit_account=debit,
            credit_account=credit,
            amount=amount,
            reason=reason,
            ref_type=ref_type,
            ref_id=ref_id,
            actor=actor,
            created_at=now,
        )

    def define_rule(
        self,
        *,
        activity: str,
        amount: int,
        daily_cap: int | None = None,
        lifetime_cap: int | None = None,
    ) -> EmissionRule:
        require_non_empty_str(activity, "activity", config=True)
        require_int_range(
            amount, "amount", 1, 1_000_000, config=True
        )
        if daily_cap is not None:
            require_int_range(
                daily_cap, "daily_cap", 1, 10_000_000, config=True
            )
            if daily_cap < amount:
                raise ConfigurationError(
                    "daily_cap must be >= amount"
                )
        if lifetime_cap is not None:
            require_int_range(
                lifetime_cap,
                "lifetime_cap",
                1,
                1_000_000_000,
                config=True,
            )
            if lifetime_cap < amount:
                raise ConfigurationError(
                    "lifetime_cap must be >= amount"
                )
        rule_id = f"RULE-{new_id()}"
        now = self._clock.now()
        try:
            with self._db.transaction() as cursor:
                cursor.execute(
                    "INSERT INTO emission_rules"
                    " (rule_id, activity, amount, daily_cap,"
                    "  lifetime_cap, active, created_at)"
                    " VALUES (?, ?, ?, ?, ?, 1, ?)",
                    (
                        rule_id,
                        activity,
                        amount,
                        daily_cap,
                        lifetime_cap,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateRuleError(
                f"activity already has a rule: {activity}"
            ) from exc
        rule = self.get_rule_by_activity(activity)
        if rule is None:
            raise IntegrityError("rule vanished after insert")
        return rule

    def get_rule_by_activity(
        self, activity: str
    ) -> EmissionRule | None:
        row = self._db.query_one(
            "SELECT * FROM emission_rules WHERE activity = ?",
            (activity,),
        )
        if row is None:
            return None
        return self._rule_from_row(row)

    def list_rules(self) -> tuple[EmissionRule, ...]:
        rows = self._db.query_all(
            "SELECT * FROM emission_rules"
            " ORDER BY created_at, rule_id"
        )
        return tuple(self._rule_from_row(row) for row in rows)

    def set_rule_active(
        self, activity: str, *, active: bool
    ) -> EmissionRule:
        rule = self.get_rule_by_activity(activity)
        if rule is None:
            raise UnknownRuleError(
                f"unknown rule activity: {activity}"
            )
        self._db.execute(
            "UPDATE emission_rules SET active = ?"
            " WHERE rule_id = ?",
            (1 if active else 0, rule.rule_id),
        )
        updated = self.get_rule_by_activity(activity)
        if updated is None:
            raise IntegrityError("rule vanished during update")
        return updated

    def _check_caps(
        self,
        cursor: sqlite3.Cursor,
        rule: EmissionRule,
        subject_zid: str,
        now: float,
    ) -> None:
        day = self._day_of(now)
        if rule.daily_cap is not None:
            row = cursor.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total"
                " FROM emission_log WHERE rule_id = ?"
                " AND subject_zid = ? AND day = ?",
                (rule.rule_id, subject_zid, day),
            ).fetchone()
            today_total = (
                int(row["total"]) if row is not None else 0
            )
            if today_total + rule.amount > rule.daily_cap:
                raise EmissionCapExceededError(
                    f"daily cap {rule.daily_cap} exceeded"
                    f" for {rule.activity}"
                    f" (today {today_total})"
                )
        if rule.lifetime_cap is not None:
            row = cursor.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total"
                " FROM emission_log WHERE rule_id = ?"
                " AND subject_zid = ?",
                (rule.rule_id, subject_zid),
            ).fetchone()
            life_total = (
                int(row["total"]) if row is not None else 0
            )
            if life_total + rule.amount > rule.lifetime_cap:
                raise EmissionCapExceededError(
                    f"lifetime cap {rule.lifetime_cap}"
                    f" exceeded for {rule.activity}"
                )

    def earn(
        self,
        *,
        subject_zid: str,
        activity: str,
        ref_type: str,
        ref_id: str,
    ) -> LedgerTransaction:
        """Mints via an active rule, enforcing caps atomically.

        The treasury row in the transaction is documentary
        (it is the mint source); the user credit is what
        moves real balance.
        """
        require_non_empty_str(subject_zid, "subject_zid")
        require_non_empty_str(ref_type, "ref_type")
        require_non_empty_str(ref_id, "ref_id")
        with self._db.transaction() as cursor:
            rule_row = cursor.execute(
                "SELECT * FROM emission_rules WHERE activity = ?",
                (activity,),
            ).fetchone()
            if rule_row is None:
                raise UnknownRuleError(
                    f"no rule for activity: {activity}"
                )
            rule = self._rule_from_row(rule_row)
            if not rule.active:
                raise RuleInactiveError(
                    f"rule {activity} is inactive"
                )
            now = self._clock.now()
            self._check_caps(cursor, rule, subject_zid, now)
            self._credit(
                cursor, subject_zid, rule.amount, now
            )
            tx = self._record_tx(
                cursor,
                kind="mint",
                debit=SYSTEM_TREASURY,
                credit=subject_zid,
                amount=rule.amount,
                reason=f"rule:{rule.rule_id}",
                ref_type=ref_type,
                ref_id=ref_id,
                actor="token-engine",
                now=now,
            )
            cursor.execute(
                "INSERT INTO emission_log"
                " (emission_id, rule_id, subject_zid, day,"
                "  amount, tx_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    f"EMI-{new_id()}",
                    rule.rule_id,
                    subject_zid,
                    self._day_of(now),
                    rule.amount,
                    tx.tx_id,
                    now,
                ),
            )
        return tx

    def grant(
        self,
        *,
        subject_zid: str,
        amount: int,
        reason: str,
        actor: str,
    ) -> LedgerTransaction:
        """Admin mint: always audited by the engine layer."""
        require_non_empty_str(subject_zid, "subject_zid")
        require_int_range(amount, "amount", 1, 10_000_000)
        require_non_empty_str(reason, "reason")
        require_non_empty_str(actor, "actor")
        now = self._clock.now()
        with self._db.transaction() as cursor:
            self._credit(cursor, subject_zid, amount, now)
            tx = self._record_tx(
                cursor,
                kind="mint",
                debit=SYSTEM_TREASURY,
                credit=subject_zid,
                amount=amount,
                reason=reason,
                ref_type="admin_grant",
                ref_id="manual",
                actor=actor,
                now=now,
            )
        return tx

    def balance(self, account: str) -> int:
        row = self._db.query_one(
            "SELECT balance FROM token_accounts"
            " WHERE account_id = ?",
            (account,),
        )
        if row is None:
            return 0
        return int(row["balance"])

    def history(
        self, account: str, *, limit: int = 50
    ) -> tuple[LedgerTransaction, ...]:
        require_int_range(limit, "limit", 1, 500)
        rows = self._db.query_all(
            "SELECT * FROM token_transactions"
            " WHERE debit_account = ? OR credit_account = ?"
            " ORDER BY created_at DESC, tx_id DESC LIMIT ?",
            (account, account, limit),
        )
        return tuple(self._tx_from_row(row) for row in rows)

    def define_item(
        self,
        *,
        item_id: str,
        title: str,
        cost: int,
        active: bool = True,
    ) -> RedemptionItem:
        require_non_empty_str(item_id, "item_id", config=True)
        require_non_empty_str(title, "title", config=True)
        require_int_range(cost, "cost", 1, 10_000_000, config=True)
        now = self._clock.now()
        self._db.execute(
            "INSERT OR REPLACE INTO redemption_items"
            " (item_id, title, cost, active, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (item_id, title, cost, 1 if active else 0, now),
        )
        item = self.get_item(item_id)
        if item is None:
            raise IntegrityError("item vanished after insert")
        return item

    def get_item(self, item_id: str) -> RedemptionItem | None:
        row = self._db.query_one(
            "SELECT * FROM redemption_items WHERE item_id = ?",
            (item_id,),
        )
        if row is None:
            return None
        return self._item_from_row(row)

    def list_items(self) -> tuple[RedemptionItem, ...]:
        rows = self._db.query_all(
            "SELECT * FROM redemption_items"
            " ORDER BY cost, item_id"
        )
        return tuple(self._item_from_row(row) for row in rows)

    def redeem(
        self, subject_zid: str, item_id: str
    ) -> RedemptionRecord:
        """Burns tokens against a catalog item, atomically."""
        require_non_empty_str(subject_zid, "subject_zid")
        require_non_empty_str(item_id, "item_id")
        with self._db.transaction() as cursor:
            item_row = cursor.execute(
                "SELECT * FROM redemption_items"
                " WHERE item_id = ?",
                (item_id,),
            ).fetchone()
            if item_row is None:
                raise UnknownItemError(
                    f"unknown item: {item_id}"
                )
            item = self._item_from_row(item_row)
            if not item.active:
                raise ItemInactiveError(
                    f"item {item_id} is inactive"
                )
            now = self._clock.now()
            self._debit(cursor, subject_zid, item.cost, now)
            tx = self._record_tx(
                cursor,
                kind="redeem",
                debit=subject_zid,
                credit=SYSTEM_BURN,
                amount=item.cost,
                reason=f"item:{item.item_id}",
                ref_type="redemption",
                ref_id=item.item_id,
                actor=subject_zid,
                now=now,
            )
            redemption_id = f"RDM-{new_id()}"
            cursor.execute(
                "INSERT INTO redemptions"
                " (redemption_id, subject_zid, item_id, cost,"
                "  tx_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    redemption_id,
                    subject_zid,
                    item.item_id,
                    item.cost,
                    tx.tx_id,
                    now,
                ),
            )
        return RedemptionRecord(
            redemption_id=redemption_id,
            subject_zid=subject_zid,
            item_id=item.item_id,
            cost=item.cost,
            tx_id=tx.tx_id,
            created_at=now,
        )

    def list_redemptions(
        self, subject_zid: str
    ) -> tuple[RedemptionRecord, ...]:
        rows = self._db.query_all(
            "SELECT * FROM redemptions WHERE subject_zid = ?"
            " ORDER BY created_at DESC, redemption_id DESC",
            (subject_zid,),
        )
        return tuple(
            RedemptionRecord(
                redemption_id=str(row["redemption_id"]),
                subject_zid=str(row["subject_zid"]),
                item_id=str(row["item_id"]),
                cost=int(row["cost"]),
                tx_id=str(row["tx_id"]),
                created_at=float(row["created_at"]),
            )
            for row in rows
        )

    def invariant_check(self) -> bool:
        """user balances == minted - redeemed (accounting law)."""
        users_row = self._db.query_one(
            "SELECT COALESCE(SUM(balance), 0) AS total"
            " FROM token_accounts WHERE account_id NOT IN"
            " (?, ?)",
            (SYSTEM_TREASURY, SYSTEM_BURN),
        )
        minted_row = self._db.query_one(
            "SELECT COALESCE(SUM(amount), 0) AS total"
            " FROM token_transactions WHERE kind = 'mint'"
        )
        redeemed_row = self._db.query_one(
            "SELECT COALESCE(SUM(amount), 0) AS total"
            " FROM token_transactions WHERE kind = 'redeem'"
        )
        user_total = (
            int(users_row["total"])
            if users_row is not None
            else 0
        )
        minted = (
            int(minted_row["total"])
            if minted_row is not None
            else 0
        )
        redeemed = (
            int(redeemed_row["total"])
            if redeemed_row is not None
            else 0
        )
        return user_total == minted - redeemed

    @staticmethod
    def _rule_from_row(row: sqlite3.Row) -> EmissionRule:
        daily_cap = row["daily_cap"]
        lifetime_cap = row["lifetime_cap"]
        return EmissionRule(
            rule_id=str(row["rule_id"]),
            activity=str(row["activity"]),
            amount=int(row["amount"]),
            daily_cap=(
                None if daily_cap is None else int(daily_cap)
            ),
            lifetime_cap=(
                None
                if lifetime_cap is None
                else int(lifetime_cap)
            ),
            active=bool(int(row["active"])),
            created_at=float(row["created_at"]),
        )

    @staticmethod
    def _item_from_row(row: sqlite3.Row) -> RedemptionItem:
        return RedemptionItem(
            item_id=str(row["item_id"]),
            title=str(row["title"]),
            cost=int(row["cost"]),
            active=bool(int(row["active"])),
            created_at=float(row["created_at"]),
        )

    @staticmethod
    def _tx_from_row(row: sqlite3.Row) -> LedgerTransaction:
        return LedgerTransaction(
            tx_id=str(row["tx_id"]),
            kind=str(row["kind"]),
            debit_account=str(row["debit_account"]),
            credit_account=str(row["credit_account"]),
            amount=int(row["amount"]),
            reason=str(row["reason"]),
            ref_type=str(row["ref_type"]),
            ref_id=str(row["ref_id"]),
            actor=str(row["actor"]),
            created_at=float(row["created_at"]),
        )

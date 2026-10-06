
"""Treasury Engine - tesoreria (NG4). Saldos SIEMPRE
2 decimales, sin sobregiro. Persistente."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

TX_TYPES = ("DEPOSIT", "WITHDRAWAL", "TRANSFER_IN",
            "TRANSFER_OUT")
_Q = "0.01"

_MIGRATIONS = (
    Migration(1, "nexo_treasury_accounts", (
        "CREATE TABLE IF NOT EXISTS nexo_treasury_accounts (account_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, account_name TEXT NOT NULL, account_kind TEXT NOT NULL DEFAULT 'BANK', bank TEXT NOT NULL DEFAULT '', currency TEXT NOT NULL DEFAULT 'USD', balance TEXT NOT NULL DEFAULT '0', active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL)",
    )),
    Migration(2, "nexo_treasury_tx", (
        "CREATE TABLE IF NOT EXISTS nexo_treasury_tx (tx_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, account_id TEXT NOT NULL, tx_type TEXT NOT NULL, amount TEXT NOT NULL, currency TEXT NOT NULL DEFAULT 'USD', counter_account TEXT NOT NULL DEFAULT '', reference TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class TreasuryEngine:
    """Bancos y caja: saldo por cuenta, movimientos."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.treasury",
                        _MIGRATIONS).run(clock)

    def create_account(self, *, company_id,
                       account_name,
                       account_kind="BANK",
                       bank="", currency="USD") \
                -> dict:
        if account_kind not in ("BANK", "CASH"):
            account_kind = "BANK"
        aid = "TRS-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " nexo_treasury_accounts"
                " (account_id, company_id,"
                " account_name, account_kind, bank,"
                " currency, balance, active,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, '0', 1,"
                " ?)",
                (aid, company_id, account_name,
                 account_kind, bank, currency, now))
        return {"account_id": aid,
                "company_id": company_id,
                "account_name": account_name,
                "account_kind": account_kind,
                "currency": currency,
                "balance": "0.00"}

    def get_account(self,
                    account_id) -> Optional[dict]:
        from decimal import Decimal as _D
        row = self._db.query_one(
            "SELECT * FROM nexo_treasury_accounts"
            " WHERE account_id = ?", (account_id,))
        if not row:
            return None
        return {"account_id": str(row["account_id"]),
                "company_id":
                    str(row["company_id"]),
                "account_name":
                    str(row["account_name"]),
                "account_kind":
                    str(row["account_kind"]),
                "currency": str(row["currency"]),
                "balance": str(_D(
                    str(row["balance"]))
                    .quantize(_D(_Q)))}

    def _move(self, cursor, account_id, delta,
              currency):
        from decimal import Decimal as _D
        row = cursor.execute(
            "SELECT balance, currency FROM"
            " nexo_treasury_accounts WHERE"
            " account_id = ?",
            (account_id,)).fetchone()
        if row is None:
            raise KeyError(account_id)
        if str(row["currency"]) != currency:
            raise ValueError(
                "moneda distinta a la cuenta")
        nb = (_D(str(row["balance"]))
              + _D(str(delta))
              ).quantize(_D(_Q))
        if nb < 0:
            raise ValueError(
                "fondos insuficientes")
        cursor.execute(
            "UPDATE nexo_treasury_accounts SET"
            " balance = ? WHERE account_id = ?",
            (str(nb), account_id))
        return nb

    def _tx(self, cursor, company_id, account_id,
            tx_type, amount, currency,
            counter_account="", reference=""):
        if tx_type not in TX_TYPES:
            raise ValueError(
                "tipo invalido: " + tx_type)
        tid = "TXT-" + str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO nexo_treasury_tx"
            " (tx_id, company_id, account_id,"
            " tx_type, amount, currency,"
            " counter_account, reference,"
            " created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (tid, company_id, account_id, tx_type,
             str(amount), currency,
             counter_account, reference,
             self._clock.now()))
        return tid

    def deposit(self, *, account_id, amount,
                reference="") -> dict:
        from decimal import Decimal as _D
        amt = _D(str(amount)).quantize(_D(_Q))
        if amt <= 0:
            raise ValueError("monto positivo")
        with self._db.transaction() as cursor:
            acc = cursor.execute(
                "SELECT company_id, currency FROM"
                " nexo_treasury_accounts WHERE"
                " account_id = ?",
                (account_id,)).fetchone()
            nb = self._move(
                cursor, account_id, str(amt),
                str(acc["currency"]))
            tid = self._tx(
                cursor, str(acc["company_id"]),
                account_id, "DEPOSIT", amt,
                str(acc["currency"]),
                reference=reference)
        return {"tx_id": tid,
                "account_id": account_id,
                "balance": str(nb)}

    def withdraw(self, *, account_id, amount,
                 reference="") -> dict:
        from decimal import Decimal as _D
        amt = _D(str(amount)).quantize(_D(_Q))
        if amt <= 0:
            raise ValueError("monto positivo")
        with self._db.transaction() as cursor:
            acc = cursor.execute(
                "SELECT company_id, currency FROM"
                " nexo_treasury_accounts WHERE"
                " account_id = ?",
                (account_id,)).fetchone()
            nb = self._move(
                cursor, account_id, "-" + str(amt),
                str(acc["currency"]))
            tid = self._tx(
                cursor, str(acc["company_id"]),
                account_id, "WITHDRAWAL", amt,
                str(acc["currency"]),
                reference=reference)
        return {"tx_id": tid,
                "account_id": account_id,
                "balance": str(nb)}

    def transfer(self, *, from_account, to_account,
                 amount, reference="") -> dict:
        from decimal import Decimal as _D
        amt = _D(str(amount)).quantize(_D(_Q))
        if amt <= 0:
            raise ValueError("monto positivo")
        with self._db.transaction() as cursor:
            fa = cursor.execute(
                "SELECT company_id, currency FROM"
                " nexo_treasury_accounts WHERE"
                " account_id = ?",
                (from_account,)).fetchone()
            cur = str(fa["currency"])
            nb1 = self._move(
                cursor, from_account,
                "-" + str(amt), cur)
            tid1 = self._tx(
                cursor, str(fa["company_id"]),
                from_account, "TRANSFER_OUT",
                amt, cur,
                counter_account=to_account,
                reference=reference)
            nb2 = self._move(
                cursor, to_account, str(amt),
                cur)
            tid2 = self._tx(
                cursor, str(fa["company_id"]),
                to_account, "TRANSFER_IN", amt,
                cur,
                counter_account=from_account,
                reference=reference)
        return {"out_tx": tid1, "in_tx": tid2,
                "from_balance": str(nb1),
                "to_balance": str(nb2)}

    def transactions_of(self, company_id,
                        period="") -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_treasury_tx"
            " WHERE company_id = ?"
            " ORDER BY created_at",
            (company_id,))
        out = []
        for r in rows:
            if period:
                import datetime
                d = datetime.datetime.fromtimestamp(
                    float(r["created_at"])
                    ).strftime("%Y-%m")
                if d != period[:7]:
                    continue
            out.append({
                "tx_id": str(r["tx_id"]),
                "account_id":
                    str(r["account_id"]),
                "tx_type": str(r["tx_type"]),
                "amount": str(r["amount"]),
                "currency": str(r["currency"]),
                "reference": str(r["reference"]),
                "created_at":
                    float(r["created_at"])})
        return out

    def position(self, company_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT account_id, account_name,"
            " account_kind, currency, balance FROM"
            " nexo_treasury_accounts WHERE"
            " company_id = ? AND active = 1"
            " ORDER BY account_name",
            (company_id,))
        return [{"account_id": str(r["account_id"]),
                 "account_name":
                     str(r["account_name"]),
                 "account_kind":
                     str(r["account_kind"]),
                 "currency": str(r["currency"]),
                 "balance": str(r["balance"])}
                for r in rows]

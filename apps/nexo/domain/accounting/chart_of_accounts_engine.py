
"""Chart of Accounts Engine - plan contable multi-pais
configurable (NG3). Cuentas jerarquicas por pais con
tipo y plantilla base. Persistente. Autocontenido."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

ACCOUNT_TYPES = ("ASSET", "LIABILITY", "EQUITY",
                 "INCOME", "EXPENSE")

_MIGRATIONS = (
    Migration(1, "nexo_chart_accounts", (
        "CREATE TABLE IF NOT EXISTS nexo_chart_accounts (account_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, country TEXT NOT NULL DEFAULT 'SV', account_code TEXT NOT NULL, account_name TEXT NOT NULL, account_type TEXT NOT NULL, parent_code TEXT NOT NULL DEFAULT '', is_postable INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL, UNIQUE(company_id, account_code))",
    )),
)

class ChartOfAccountsEngine:
    """Plan contable por empresa y pais."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.chart",
                        _MIGRATIONS).run(clock)

    def add_account(self, *, company_id, account_code,
                    account_name, account_type,
                    country="SV", parent_code="",
                    is_postable=True) -> dict:
        if account_type not in ACCOUNT_TYPES:
            raise ValueError(
                "tipo invalido: " + str(account_type))
        aid = "COA-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_chart_accounts"
                " (account_id, company_id, country,"
                " account_code, account_name,"
                " account_type, parent_code,"
                " is_postable, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (aid, company_id, country,
                 account_code, account_name,
                 account_type, parent_code,
                 1 if is_postable else 0, now))
        return {"account_id": aid,
                "company_id": company_id,
                "account_code": account_code,
                "account_name": account_name,
                "account_type": account_type,
                "country": country,
                "parent_code": parent_code,
                "is_postable": is_postable}

    def install_template(self, *, company_id,
                         country="SV") -> dict:
        creadas = 0
        base = [
            ("1000", "Efectivo y equivalentes",
             "ASSET", ""),
            ("1100", "Cuentas por cobrar",
             "ASSET", ""),
            ("1500", "Activos fijos", "ASSET", ""),
            ("2000", "Cuentas por pagar",
             "LIABILITY", ""),
            ("2100", "Impuestos por pagar",
             "LIABILITY", ""),
            ("3000", "Capital social", "EQUITY", ""),
            ("3100", "Utilidades retenidas",
             "EQUITY", ""),
            ("4000", "Ingresos por ventas",
             "INCOME", ""),
            ("5000", "Costo de ventas",
             "EXPENSE", ""),
            ("6000", "Gastos operativos",
             "EXPENSE", ""),
            ("6100", "Gastos de personal",
             "EXPENSE", "6000"),
            ("6200", "Costos logisticos",
             "EXPENSE", "6000"),
        ]
        for code, name, atype, parent in base:
            self.add_account(
                company_id=company_id,
                account_code=code,
                account_name=name,
                account_type=atype,
                country=country,
                parent_code=parent)
            creadas = creadas + 1
        return {"company_id": company_id,
                "country": country,
                "accounts_created": creadas}

    def get_account(self, company_id,
                    account_code) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_chart_accounts"
            " WHERE company_id = ? AND account_code"
            " = ?", (company_id, account_code))
        return self._row(row) if row else None

    def _row(self, r) -> dict:
        return {"account_id": str(r["account_id"]),
                "company_id": str(r["company_id"]),
                "country": str(r["country"]),
                "account_code": str(r["account_code"]),
                "account_name": str(r["account_name"]),
                "account_type": str(r["account_type"]),
                "parent_code": str(r["parent_code"]),
                "is_postable": bool(r["is_postable"])}

    def accounts_of(self, company_id,
                    country="") -> List[dict]:
        if country:
            rows = self._db.query_all(
                "SELECT * FROM nexo_chart_accounts"
                " WHERE company_id = ? AND country = ?"
                " ORDER BY account_code",
                (company_id, country))
        else:
            rows = self._db.query_all(
                "SELECT * FROM nexo_chart_accounts"
                " WHERE company_id = ?"
                " ORDER BY account_code",
                (company_id,))
        return [self._row(r) for r in rows]

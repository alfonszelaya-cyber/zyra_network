
from __future__ import annotations
from decimal import Decimal
from apps.nexo.domain.accounting.accounting_engine import (
    AccountingEngine)
from apps.nexo.domain.accounting.journal_engine import (
    JournalEngine)

class CreateJournalEntryUseCase:
    """Crea asiento de partida doble."""

    def __init__(self, accounting_engine: AccountingEngine,
                 journal_engine: JournalEngine) -> None:
        self._engine = accounting_engine
        self._journal = journal_engine

    def execute(self, *, company_id: str,
                debit_account: str, credit_account: str,
                amount, description: str,
                created_by: str) -> dict:
        amt = Decimal(str(amount))
        if amt <= 0:
            raise ValueError(
                "Amount must be greater than zero")
        d = self._engine.create_entry(
            account_code=debit_account, amount=amt,
            entry_type="DEBIT",
            description=description,
            reference_id=company_id)
        c = self._engine.create_entry(
            account_code=credit_account, amount=amt,
            entry_type="CREDIT",
            description=description,
            reference_id=company_id)
        self._journal.register_entry(d)
        self._journal.register_entry(c)
        return {"entry_id": d["entry_id"],
                "debit": d, "credit": c,
                "amount": str(amt),
                "company_id": company_id,
                "created_by": created_by,
                "status": "POSTED"}

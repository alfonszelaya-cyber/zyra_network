
"""Gateway NEXO Finance (fachada del dominio, NO motor).

Regla 69: domain/finance ya es el dueno de la logica
financiera de NEXO. Este gateway expone esas capacidades
al ecosistema y reporta estado honesto (sin falsos OK)."""
from __future__ import annotations

class NexoFinanceGateway:
    """Fachada fina sobre los engines financieros NEXO."""

    def __init__(self, finanzas_total=None,
                 declaration_engine=None,
                 tax_declarations=None,
                 fiscal_document_engine=None):
        self._fin = finanzas_total
        self._dec = declaration_engine
        self._tax = tax_declarations
        self._fdoc = fiscal_document_engine

    def capabilities(self) -> dict:
        return {"finance_master":
                    self._fin is not None,
                "declarations":
                    self._dec is not None,
                "tax_declarations":
                    self._tax is not None,
                "fiscal_documents":
                    self._fdoc is not None}

    def declare_tax(self, **kwargs) -> dict:
        if self._tax is not None:
            for name in ("declare", "create_declaration",
                         "submit"):
                m = getattr(self._tax, name, None)
                if callable(m):
                    r = m(**kwargs)
                    return (r if isinstance(r, dict)
                            else {"result": r})
        return {"status": "not_configured",
                "reason": "tax_declarations no inyectado"}

    def fiscal_summary(self, **kwargs) -> dict:
        if self._fin is not None:
            for name in ("summary", "resumen", "status"):
                m = getattr(self._fin, name, None)
                if callable(m):
                    r = m(**kwargs)
                    return (r if isinstance(r, dict)
                            else {"result": r})
        return {"status": "not_configured",
                "reason": "finanzas_total no inyectado"}

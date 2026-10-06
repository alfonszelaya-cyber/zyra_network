
"""Gateway NEXO -> AIChain transversal (regla 69).

Firma real: analyze(prompt, content) -> AIResult.
Clasificacion de documentos contables. Si la IA real
esta disponible delega; si no, reglas simples locales
marcadas (catalogo NexoStore: venta/compra/pago/cobro/
ajuste)."""
from __future__ import annotations

RULES = (
    ("venta", ("venta", "factura de venta", "invoice",
               "sold")),
    ("compra", ("compra", "purchase", "proveedor")),
    ("pago", ("pago", "payment", "abono")),
    ("cobro", ("cobro", "cobranza", "receipt")),
    ("ajuste", ("ajuste", "adjustment",
                "correccion")),
)

class NexoAIGateway:
    """Clasificador de documentos contables NEXO."""

    def __init__(self, chain=None):
        self._chain = chain

    @property
    def mode(self) -> str:
        return ("ai_chain"
                if self._chain is not None
                else "rules_fallback")

    def _rules_classify(self, text):
        t = (text or "").lower()
        best, hits = None, 0
        for cat, kws in RULES:
            c = sum(1 for k in kws if k in t)
            if c > hits:
                best, hits = cat, c
        return (best or "ajuste",
                0.6 if hits else 0.3)

    def classify_document(self, text) -> dict:
        if self._chain is not None:
            try:
                r = self._chain.analyze(
                    "clasifica documento contable "
                    "en venta/compra/pago/cobro/ajuste",
                    text)
                cat = (getattr(r, "verdict", None)
                       or getattr(r, "category", None)
                       or (r.get("category")
                           if isinstance(r, dict)
                           else None)
                       or str(r))
                conf = getattr(r, "confidence", None)
                out = {"category": str(cat),
                       "source": self.mode}
                if conf is not None:
                    out["confidence"] = float(conf)
                return out
            except Exception:
                pass
        cat, conf = self._rules_classify(text)
        return {"category": cat,
                "confidence": conf,
                "source": self.mode}

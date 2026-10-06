
"""Nexo Business Metrics - KPIs de negocio (NG7)."""
from __future__ import annotations
from decimal import Decimal as _D
from typing import Dict

_Q = "0.01"

class NexoBusinessMetrics:
    """KPIs: crecimiento, margen, snapshot."""

    def growth_rate(self, current,
                    previous) -> float:
        prev = _D(str(previous))
        if prev <= 0:
            return 0.0
        cur = _D(str(current))
        g = ((cur - prev) / prev) * _D("100")
        return float(g.quantize(_D(_Q)))

    def profit_margin(self, income,
                      expense) -> float:
        inc = _D(str(income))
        if inc <= 0:
            return 0.0
        exp = _D(str(expense))
        m = ((inc - exp) / inc) * _D("100")
        return float(m.quantize(_D(_Q)))

    def snapshot(self, *, income, expense,
                 previous_income="0") -> Dict:
        return {"income": str(_D(str(income))
                              .quantize(_D(_Q))),
                "expense": str(_D(str(expense))
                               .quantize(_D(_Q))),
                "net": str((_D(str(income))
                            - _D(str(expense))
                            ).quantize(_D(_Q))),
                "growth_pct": self.growth_rate(
                    income, previous_income),
                "margin_pct": self.profit_margin(
                    income, expense)}

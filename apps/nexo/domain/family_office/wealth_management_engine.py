
"""Wealth Management - NEXO / ZYRA (migrado mejorado)."""
from __future__ import annotations
from typing import Dict
from datetime import datetime

class WealthManagementEngine:
    """Gestion global de patrimonio."""

    def _now(self):
        return datetime.utcnow().isoformat()

    def generate_wealth_snapshot(self, *,
                                 total_assets, total_liabilities):
        from decimal import Decimal as _D
        a = _D(str(total_assets))
        l = _D(str(total_liabilities))
        net = a - l
        return {"generated_at": self._now(),
                "total_assets": str(a),
                "total_liabilities": str(l),
                "net_worth": str(net),
                "status": "ACTIVE"}

    def calculate_growth(self, *, current_value,
                         previous_value):
        from decimal import Decimal as _D
        prev = _D(str(previous_value))
        if prev <= 0:
            return 0.0
        cur = _D(str(current_value))
        growth = ((cur - prev) / prev) * 100
        return float(round(growth, 2))

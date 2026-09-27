
"""Reporte consolidado de gobierno para AGRO."""
from __future__ import annotations


class GovernmentReport:
    def __init__(self, store) -> None:
        self._store = store

    def consolidated(self) -> dict:
        s = self._store.summary()
        return {
            "producers_total": int(
                s.get("producers_total") or 0
            ),
            "producers_verified": int(
                s.get("producers_verified") or 0
            ),
            "producers_by_role": dict(
                s.get("producers_by_role") or {}
            ),
            "productions_by_product": dict(
                s.get("productions_by_product") or {}
            ),
            "aid_total": int(s.get("aid_total") or 0),
            "aid_by_status": dict(
                s.get("aid_by_status") or {}
            ),
            "aid_by_program": dict(
                s.get("aid_by_program") or {}
            ),
        }


"""Reporte de ayudas de gobierno: beneficiados y
no beneficiados, para cerrar brechas de cobertura."""
from __future__ import annotations


class GovernmentAidService:
    def __init__(self, store) -> None:
        self._store = store

    def beneficiaries_report(self) -> dict:
        aid = list(self._store.list_aid())
        producers = list(self._store.list_producers())
        counts = {}
        for a in aid:
            pid = str(a.get("producer_id") or "")
            if pid:
                counts[pid] = counts.get(pid, 0) + 1
        beneficiados = []
        no_beneficiados = []
        for p in producers:
            pid = str(p.get("producer_id") or "")
            row = {
                "producer_id": pid,
                "name": str(p.get("name") or ""),
                "role": str(p.get("role") or ""),
                "verified": bool(p.get("verified")),
            }
            if pid in counts:
                row["aid_count"] = counts[pid]
                beneficiados.append(row)
            else:
                no_beneficiados.append(row)
        return {
            "aid_total": len(aid),
            "beneficiados": beneficiados,
            "no_beneficiados": no_beneficiados,
        }

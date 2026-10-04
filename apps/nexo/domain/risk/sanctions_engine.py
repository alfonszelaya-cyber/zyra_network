
"""Sanctions Screening - NEXO / ZYRA (informa, no bloquea)."""
from __future__ import annotations
from datetime import datetime
from typing import Dict, List
import uuid

class SanctionsEngine:
    def __init__(self):
        self._history = []

    def evaluate(self, *, entity_data):
        sanctioned = entity_data.get("sanctioned", False)
        score = 100 if sanctioned else 0
        r = {"sanction_id": f"SAN-{uuid.uuid4()}", "entity_id": entity_data.get("entity_id"),
             "entity_name": entity_data.get("entity_name"), "sanctioned": sanctioned,
             "score": score, "generated_at": datetime.utcnow().isoformat(),
             "status": "SCREENED"}
        self._history.append(r)
        return r


"""Nexo Notification Registry - consultas agregadas."""
from __future__ import annotations
from typing import Dict
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database

class NexoNotificationRegistry:
    """Consultas agregadas de notificaciones."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock

    def counts_by_status(self) -> Dict[str, int]:
        rows = self._db.query_all(
            "SELECT status, COUNT(*) AS c FROM"
            " nexo_notifications GROUP BY status")
        return {str(r["status"]): int(r["c"])
                for r in rows}

    def counts_by_channel(self) -> Dict[str, int]:
        rows = self._db.query_all(
            "SELECT channel, COUNT(*) AS c FROM"
            " nexo_notifications GROUP BY channel")
        return {str(r["channel"]): int(r["c"])
                for r in rows}


from __future__ import annotations

class DispatchNotificationUseCase:
    """Despacha una o todas las pendientes."""

    def __init__(self, notification_engine):
        self._eng = notification_engine

    def execute(self, *,
                notification_id=None) -> dict:
        if notification_id:
            return {"dispatched":
                        self._eng.dispatch(
                            notification_id)}
        pend = self._eng.pending()
        results = []
        for n in pend:
            results.append(self._eng.dispatch(
                n["notification_id"]))
        sent = sum(1 for r in results
                   if r["status"] == "SENT")
        return {"processed": len(results),
                "sent": sent,
                "results": results}

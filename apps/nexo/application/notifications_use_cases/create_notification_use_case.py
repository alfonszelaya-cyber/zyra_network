
from __future__ import annotations

class CreateNotificationUseCase:
    """Crea notificacion validada."""

    def __init__(self, notification_engine):
        self._eng = notification_engine

    def execute(self, *, recipient, subject,
                body="", channel="in_app",
                company_id="") -> dict:
        return self._eng.create_notification(
            recipient=recipient, subject=subject,
            body=body, channel=channel,
            company_id=company_id)

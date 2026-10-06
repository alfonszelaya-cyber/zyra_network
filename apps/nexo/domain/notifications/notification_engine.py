
"""Nexo Notification Engine - notificaciones NEXO
(persistente). Cola PENDING -> SENT/FAILED con
reintentos. Canal inyectado; sin canal ->
not_configured honesto."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_notifications", (
        "CREATE TABLE IF NOT EXISTS nexo_notifications (notification_id TEXT PRIMARY KEY, company_id TEXT NOT NULL DEFAULT '', channel TEXT NOT NULL DEFAULT 'in_app', recipient TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, sent_at REAL)",
    )),
)

class NexoNotificationEngine:
    """Notificaciones NEXO (cola persistente)."""

    def __init__(self, db, clock, channel=None):
        self._db = db
        self._clock = clock
        self._channel = channel
        MigrationRunner(db, "nexo.notify",
                        _MIGRATIONS).run(clock)

    def create_notification(self, *, recipient,
                            subject, body="",
                            channel="in_app",
                            company_id="") -> dict:
        if not str(recipient).strip():
            raise ValueError(
                "recipient requerido")
        if not str(subject).strip():
            raise ValueError(
                "subject requerido")
        nid = "NTF-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_notifications"
                " (notification_id, company_id,"
                " channel, recipient, subject, body,"
                " status, attempts, error,"
                " created_at, sent_at)"
                " VALUES (?, ?, ?, ?, ?, ?,"
                " 'PENDING', 0, '', ?, NULL)",
                (nid, company_id, channel,
                 recipient, subject, body, now))
        return self.get(nid)

    def get(self, notification_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_notifications"
            " WHERE notification_id = ?",
            (notification_id,))
        if not row:
            return None
        return {"notification_id":
                    str(row["notification_id"]),
                "company_id":
                    str(row["company_id"]),
                "channel": str(row["channel"]),
                "recipient": str(row["recipient"]),
                "subject": str(row["subject"]),
                "body": str(row["body"]),
                "status": str(row["status"]),
                "attempts": int(row["attempts"]),
                "error": str(row["error"]),
                "created_at":
                    float(row["created_at"]),
                "sent_at": (float(row["sent_at"])
                            if row["sent_at"]
                            else None)}

    def pending(self, limit=50) -> List[dict]:
        rows = self._db.query_all(
            "SELECT notification_id FROM"
            " nexo_notifications WHERE"
            " status = 'PENDING'"
            " ORDER BY created_at LIMIT ?",
            (limit,))
        return [self.get(str(r["notification_id"]))
                for r in rows]

    def _send_channel(self, n) -> dict:
        if self._channel is None:
            return {"ok": False,
                    "error": "not_configured"}
        for name in ("send", "notify", "push"):
            m = getattr(self._channel, name, None)
            if callable(m):
                try:
                    r = m(recipient=n["recipient"],
                          subject=n["subject"],
                          body=n["body"])
                    return {"ok": True,
                            "result": (r if
                                       isinstance(r, dict)
                                       else
                                       {"raw": str(r)})}
                except TypeError:
                    continue
                except Exception as e:
                    return {"ok": False,
                            "error": str(e)[:200]}
        return {"ok": False,
                "error": "canal sin metodo send"}

    def dispatch(self, notification_id) -> dict:
        n = self.get(notification_id)
        if not n:
            raise KeyError(notification_id)
        if n["status"] == "SENT":
            return n
        r = self._send_channel(n)
        now = self._clock.now()
        if r["ok"]:
            self._db.execute(
                "UPDATE nexo_notifications SET"
                " status = 'SENT', sent_at = ?,"
                " attempts = attempts + 1 WHERE"
                " notification_id = ?",
                (now, notification_id))
        else:
            self._db.execute(
                "UPDATE nexo_notifications SET"
                " status = 'FAILED', error = ?,"
                " attempts = attempts + 1 WHERE"
                " notification_id = ?",
                (r.get("error", ""),
                 notification_id))
        return self.get(notification_id)

    def retry_failed(self) -> int:
        rows = self._db.query_all(
            "SELECT notification_id FROM"
            " nexo_notifications WHERE"
            " status = 'FAILED' LIMIT 50")
        count = 0
        for r in rows:
            got = self.get(
                str(r["notification_id"]))
            self._db.execute(
                "UPDATE nexo_notifications SET"
                " status = 'PENDING' WHERE"
                " notification_id = ?",
                (got["notification_id"],))
            count = count + 1
        return count

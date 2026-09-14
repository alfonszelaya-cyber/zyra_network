"""AXIS Life History -> Network Outbox bridge."""
from __future__ import annotations


_EVENT_TO_LIFE = {
    "birth_registered": "life.birth.registered",
    "zid_biometric_upgrade": "life.zid.biometric_upgrade",
    "health_exam": "life.health.event",
    "health_result": "life.health.event",
    "health_appointment": "life.health.event",
    "justice_case": "life.justice.event",
    "justice_status": "life.justice.event",
    "security_incident": "life.security.event",
    "security_status": "life.security.event",
}


class OutboxBridge:
    def __init__(self, *, life, outbox, clock):
        self._life = life
        self._outbox = outbox
        self._clock = clock
        self._life._store._db.execute(
            "CREATE TABLE IF NOT EXISTS"
            " life_outbox_sent ("
            " event_id TEXT PRIMARY KEY,"
            " sent_at REAL NOT NULL)"
        )

    def sync_pending(self):
        emitted = 0
        skipped = 0
        rows = self._life._store._db.query_all(
            "SELECT event_id, person_id,"
            " event_type, detail, occurred_at"
            " FROM life_events"
            " ORDER BY occurred_at, rowid"
        )
        for row in rows:
            event_id = str(row["event_id"])
            already = self._life._store._db.query_one(
                "SELECT 1 FROM life_outbox_sent"
                " WHERE event_id = ?",
                (event_id,),
            )
            if already is not None:
                skipped += 1
                continue
            etype = str(row["event_type"])
            network_type = _EVENT_TO_LIFE.get(etype)
            if network_type is None:
                continue
            try:
                self._outbox.enqueue(
                    {
                        "event_id": event_id,
                        "event_type": network_type,
                        "aggregate_id": str(
                            row["person_id"]
                        ),
                        "payload": {
                            "detail": str(
                                row["detail"] or ""
                            ),
                            "source": "axis",
                        },
                    }
                )
            except Exception:
                continue
            self._life._store._db.execute(
                "INSERT INTO life_outbox_sent"
                " (event_id, sent_at) VALUES (?, ?)",
                (event_id, self._clock.now()),
            )
            emitted += 1
        return {
            "emitted": emitted,
            "skipped": skipped,
        }

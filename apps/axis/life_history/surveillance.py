"""AXIS Surveillance - camera feed analysis."""
import unittest

from apps.axis.life_history.service import (
    LifeHistoryService,
)


class SurveillanceService:
    def __init__(self, *, life, provider):
        self._life = life
        self._provider = provider
        self._life._store._db.execute(
            "CREATE TABLE IF NOT EXISTS"
            " surveillance_alerts ("
            " alert_id TEXT PRIMARY KEY,"
            " person_id TEXT,"
            " matched_zid TEXT,"
            " confidence REAL,"
            " operator TEXT NOT NULL,"
            " created_at REAL NOT NULL)"
        )

    def identify(self, *, camera_frame, operator):
        if not operator.strip():
            raise ValueError("operator required")
        probe = self._provider.extract_template(
            camera_frame
        )
        rows = self._life._store._db.query_all(
            "SELECT person_id, zid, full_name"
            " FROM life_persons WHERE zid"
            " IS NOT NULL"
        )
        best_score = 0.0
        best = None
        for row in rows:
            stored = self._provider.get_known_template(
                str(row["zid"])
            )
            if stored is None:
                continue
            score = self._provider.compare(
                probe, stored
            )
            if score > best_score:
                best_score = score
                best = row
        threshold = (
            self._provider.match_threshold
        )
        now = self._life._store._clock.now()
        alert_id = (
            "SUR-"
            + str(now)[:10].replace(".", "")
            + "-"
            + str(len(rows))
        )
        if best is None or best_score < threshold:
            with self._life._store._db.transaction() as cursor:
                cursor.execute(
                    "INSERT INTO"
                    " surveillance_alerts ("
                    " alert_id, person_id,"
                    " matched_zid, confidence,"
                    " operator, created_at)"
                    " VALUES (?,?,?,?,?,?)",
                    (
                        alert_id,
                        None,
                        None,
                        best_score,
                        operator,
                        now,
                    ),
                )
            return {
                "alert_id": alert_id,
                "matched": False,
                "zid": None,
                "confidence": best_score,
                "threshold": threshold,
            }
        zid = str(best["zid"])
        person_id = str(best["person_id"])
        with self._life._store._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " surveillance_alerts ("
                " alert_id, person_id,"
                " matched_zid, confidence,"
                " operator, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (
                    alert_id,
                    person_id,
                    zid,
                    best_score,
                    operator,
                    now,
                ),
            )
            self._life._store._chain_event(
                cursor,
                person_id=person_id,
                actor=operator,
                event_type="security_alert",
                detail=alert_id + " camera match",
                now=now,
            )
        return {
            "alert_id": alert_id,
            "matched": True,
            "zid": zid,
            "person_name": str(
                best["full_name"]
            ),
            "confidence": best_score,
            "threshold": threshold,
        }

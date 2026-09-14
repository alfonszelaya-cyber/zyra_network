"""Life History repository - read-side queries."""
from __future__ import annotations

from apps.axis.life_history.store import (
    LifeHistoryStore,
)


class LifeHistoryRepository:
    def __init__(
        self, store: LifeHistoryStore,
    ) -> None:
        self._store = store

    def births_between(
        self,
        *,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, object]]:
        rows = self._store._db.query_all(
            "SELECT birth_id, person_id,"
            " birth_date, birth_place,"
            " status FROM life_births"
            " WHERE birth_date >= ?"
            " AND birth_date <= ?"
            " ORDER BY rowid",
            (date_from, date_to),
        )
        return [
            {
                "birth_id": str(
                    r["birth_id"]
                ),
                "person_id": str(
                    r["person_id"]
                ),
                "birth_date": str(
                    r["birth_date"]
                ),
                "birth_place": str(
                    r["birth_place"]
                ),
                "status": str(
                    r["status"]
                ),
            }
            for r in rows
        ]

    def registry_size(self) -> int:
        row = self._store._db.query_one(
            "SELECT COUNT(*) AS n FROM"
            " life_births"
        )
        return (
            int(row["n"])
            if row is not None
            else 0
        )

    def unbound_persons(self) -> list[str]:
        rows = self._store._db.query_all(
            "SELECT person_id FROM"
            " life_persons WHERE zid"
            " IS NULL ORDER BY rowid"
        )
        return [
            str(r["person_id"])
            for r in rows
        ]

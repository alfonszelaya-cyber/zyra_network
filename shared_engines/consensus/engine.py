"""Distributed consensus: membership, terms, votes,
quorum leader election and fenced leases.

Durability: every mutation runs in one SQLite
transaction. Fencing: the lease fencing token IS
the consensus term - a new term invalidates every
lease granted in an older term, so a stale holder
can never act on stale authority.
"""
from __future__ import annotations

from shared_engines.common.clocks import Clock
from shared_engines.common.validation import (
    require_int_range,
    require_non_empty_str,
    require_positive_number,
)
from shared_engines.consensus.contracts import (
    LeaseState,
)
from shared_engines.consensus.errors import (
    AlreadyVotedError,
    ConsensusError,
    LeaseHeldError,
    NoLeaseError,
)
from shared_engines.storage.database import (
    Database,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

_MIGRATIONS = (
    Migration(
        1,
        "consensus",
        (
            "CREATE TABLE consensus_members ("
            " member_id TEXT PRIMARY KEY,"
            " joined_at REAL NOT NULL,"
            " active INTEGER NOT NULL"
            " DEFAULT 1)",
            "CREATE TABLE consensus_state ("
            " key TEXT PRIMARY KEY,"
            " value TEXT NOT NULL)",
            "CREATE TABLE consensus_votes ("
            " term INTEGER NOT NULL,"
            " voter_id TEXT NOT NULL,"
            " candidate_id TEXT NOT NULL,"
            " PRIMARY KEY (term, voter_id))",
            "CREATE TABLE consensus_leases ("
            " resource TEXT PRIMARY KEY,"
            " holder_id TEXT NOT NULL,"
            " term INTEGER NOT NULL,"
            " expires_at REAL NOT NULL)",
        ),
    ),
)


class ConsensusEngine:
    """Term-based consensus with fenced leases."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        member_id: str,
    ) -> None:
        require_non_empty_str(
            member_id, "member_id"
        )
        self._db = db
        self._clock = clock
        self._member_id = member_id
        MigrationRunner(
            db, "consensus", _MIGRATIONS
        ).run(clock)
        row = db.query_one(
            "SELECT value FROM"
            " consensus_state"
            " WHERE key = 'term'"
        )
        if row is None:
            with db.transaction() as cursor:
                cursor.execute(
                    "INSERT OR IGNORE INTO"
                    " consensus_state"
                    " (key, value) VALUES"
                    " ('term', '0')"
                )

    def register_member(
        self, member_id: str
    ) -> None:
        require_non_empty_str(
            member_id, "member_id"
        )
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " consensus_members"
                " (member_id, joined_at,"
                " active) VALUES (?, ?, 1)"
                " ON CONFLICT(member_id)"
                " DO UPDATE SET active = 1",
                (
                    member_id,
                    self._clock.now(),
                ),
            )

    def deactivate_member(
        self, member_id: str
    ) -> None:
        require_non_empty_str(
            member_id, "member_id"
        )
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE consensus_members"
                " SET active = 0"
                " WHERE member_id = ?",
                (member_id,),
            )

    def active_members(
        self,
    ) -> tuple[str, ...]:
        rows = self._db.query_all(
            "SELECT member_id FROM"
            " consensus_members"
            " WHERE active = 1"
            " ORDER BY member_id"
        )
        return tuple(
            str(r["member_id"])
            for r in rows
        )

    def member_count(self) -> int:
        row = self._db.query_one(
            "SELECT COUNT(*) AS n FROM"
            " consensus_members"
            " WHERE active = 1"
        )
        return (
            int(row["n"])
            if row is not None
            else 0
        )

    def quorum_size(self) -> int:
        return (
            self.member_count() // 2 + 1
        )

    def current_term(self) -> int:
        row = self._db.query_one(
            "SELECT value FROM"
            " consensus_state"
            " WHERE key = 'term'"
        )
        if row is None:
            raise ConsensusError(
                "consensus state missing"
            )
        return int(str(row["value"]))

    def leader(self) -> str | None:
        row = self._db.query_one(
            "SELECT value FROM"
            " consensus_state"
            " WHERE key = 'leader'"
        )
        if row is None:
            return None
        value = str(row["value"])
        return value or None

    def _require_active(
        self, member_id: str
    ) -> None:
        row = self._db.query_one(
            "SELECT active FROM"
            " consensus_members"
            " WHERE member_id = ?",
            (member_id,),
        )
        if row is None or int(
            row["active"]
        ) != 1:
            raise ConsensusError(
                "member not active:"
                f" {member_id}"
            )

    def start_new_term(self) -> int:
        with self._db.transaction() as cursor:
            row = cursor.execute(
                "SELECT value FROM"
                " consensus_state"
                " WHERE key = 'term'"
            ).fetchone()
            term = (
                int(str(row["value"])) + 1
                if row is not None
                else 1
            )
            cursor.execute(
                "INSERT INTO"
                " consensus_state"
                " (key, value) VALUES"
                " ('term', ?)"
                " ON CONFLICT(key) DO"
                " UPDATE SET value ="
                " excluded.value",
                (str(term),),
            )
            cursor.execute(
                "DELETE FROM"
                " consensus_state"
                " WHERE key = 'leader'"
            )
        return term

    def vote(
        self,
        *,
        term: int,
        candidate_id: str,
    ) -> None:
        require_int_range(
            term, "term", 1, 2**62
        )
        require_non_empty_str(
            candidate_id, "candidate_id"
        )
        self._require_active(
            self._member_id
        )
        if term != self.current_term():
            raise ConsensusError(
                f"stale term {term}:"
                " current term is"
                f" {self.current_term()}"
            )
        from sqlite3 import IntegrityError

        try:
            with (
                self._db.transaction()
                as cursor
            ):
                cursor.execute(
                    "INSERT INTO"
                    " consensus_votes"
                    " (term, voter_id,"
                    " candidate_id)"
                    " VALUES (?, ?, ?)",
                    (
                        term,
                        self._member_id,
                        candidate_id,
                    ),
                )
        except IntegrityError as exc:
            raise AlreadyVotedError(
                "member"
                f" {self._member_id}"
                " already voted in term"
                f" {term}"
            ) from exc

    def elect_leader(
        self, *, term: int
    ) -> str:
        if term != self.current_term():
            raise ConsensusError(
                f"stale term {term}"
            )
        rows = self._db.query_all(
            "SELECT candidate_id,"
            " COUNT(*) AS n FROM"
            " consensus_votes"
            " WHERE term = ?"
            " GROUP BY candidate_id"
            " ORDER BY n DESC,"
            " candidate_id ASC",
            (term,),
        )
        if not rows:
            raise ConsensusError(
                "no votes in term"
                f" {term}"
            )
        top = int(rows[0]["n"])
        quorum = self.quorum_size()
        if top < quorum:
            raise ConsensusError(
                "quorum not reached:"
                f" best has {top}/"
                f"{quorum} votes"
            )
        if len(rows) > 1 and int(
            rows[1]["n"]
        ) >= top:
            raise ConsensusError(
                "contested election:"
                " tie at top"
            )
        elected = str(
            rows[0]["candidate_id"]
        )
        self._require_active(elected)
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " consensus_state"
                " (key, value) VALUES"
                " ('leader', ?)"
                " ON CONFLICT(key) DO"
                " UPDATE SET value ="
                " excluded.value",
                (elected,),
            )
        return elected

    def acquire_lease(
        self,
        *,
        resource: str,
        holder_id: str,
        lease_seconds: float,
    ) -> int:
        require_non_empty_str(
            resource, "resource"
        )
        self._require_active(holder_id)
        require_positive_number(
            lease_seconds, "lease_seconds"
        )
        now = self._clock.now()
        term = self.current_term()
        with self._db.transaction() as cursor:
            row = cursor.execute(
                "SELECT holder_id, term,"
                " expires_at FROM"
                " consensus_leases"
                " WHERE resource = ?",
                (resource,),
            ).fetchone()
            if row is not None:
                held_by = str(
                    row["holder_id"]
                )
                lease_term = int(
                    row["term"]
                )
                expires = float(
                    row["expires_at"]
                )
                if (
                    lease_term == term
                    and expires > now
                    and held_by
                    != holder_id
                ):
                    raise LeaseHeldError(
                        "lease"
                        f" '{resource}'"
                        " held by"
                        f" '{held_by}'"
                        " (fencing"
                        f" {lease_term})"
                    )
            cursor.execute(
                "INSERT INTO"
                " consensus_leases"
                " (resource, holder_id,"
                " term, expires_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(resource)"
                " DO UPDATE SET"
                " holder_id ="
                " excluded.holder_id,"
                " term = excluded.term,"
                " expires_at ="
                " excluded.expires_at",
                (
                    resource,
                    holder_id,
                    term,
                    now + lease_seconds,
                ),
            )
        return term

    def renew_lease(
        self,
        *,
        resource: str,
        holder_id: str,
        lease_seconds: float,
    ) -> int:
        require_non_empty_str(
            resource, "resource"
        )
        require_positive_number(
            lease_seconds, "lease_seconds"
        )
        now = self._clock.now()
        term = self.current_term()
        with self._db.transaction() as cursor:
            row = cursor.execute(
                "SELECT holder_id, term"
                " FROM consensus_leases"
                " WHERE resource = ?",
                (resource,),
            ).fetchone()
            if row is None:
                raise NoLeaseError(
                    "no lease for"
                    f" '{resource}'"
                )
            holder = str(
                row["holder_id"]
            )
            lease_term = int(row["term"])
            if holder != holder_id:
                raise LeaseHeldError(
                    "lease"
                    f" '{resource}' held"
                    f" by '{holder}'"
                )
            if lease_term != term:
                raise NoLeaseError(
                    f"lease '{resource}'"
                    " fenced: term"
                    f" {lease_term} !="
                    f" {term}"
                )
            cursor.execute(
                "UPDATE consensus_leases"
                " SET expires_at = ?"
                " WHERE resource = ?",
                (
                    now + lease_seconds,
                    resource,
                ),
            )
        return term

    def release_lease(
        self,
        *,
        resource: str,
        holder_id: str,
    ) -> None:
        require_non_empty_str(
            resource, "resource"
        )
        with self._db.transaction() as cursor:
            row = cursor.execute(
                "SELECT holder_id FROM"
                " consensus_leases"
                " WHERE resource = ?",
                (resource,),
            ).fetchone()
            if row is None:
                raise NoLeaseError(
                    "no lease for"
                    f" '{resource}'"
                )
            if str(
                row["holder_id"]
            ) != holder_id:
                raise LeaseHeldError(
                    "lease"
                    f" '{resource}' held"
                    " by someone else"
                )
            cursor.execute(
                "DELETE FROM"
                " consensus_leases"
                " WHERE resource = ?",
                (resource,),
            )

    def lease_holder(
        self, resource: str
    ) -> LeaseState | None:
        require_non_empty_str(
            resource, "resource"
        )
        row = self._db.query_one(
            "SELECT * FROM"
            " consensus_leases"
            " WHERE resource = ?",
            (resource,),
        )
        if row is None:
            return None
        return LeaseState(
            resource=str(
                row["resource"]
            ),
            holder_id=str(
                row["holder_id"]
            ),
            fencing_token=int(
                row["term"]
            ),
            expires_at=float(
                row["expires_at"]
            ),
        )

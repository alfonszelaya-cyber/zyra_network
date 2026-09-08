"""Consensus proofs: quorum, vote-once, leader
election, term fencing of leases."""
from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.consensus.engine import (
    ConsensusEngine,
)
from shared_engines.consensus.errors import (
    AlreadyVotedError,
    ConsensusError,
    LeaseHeldError,
    NoLeaseError,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)


def _cluster(
    tmp_path: Path,
) -> tuple[
    SQLiteAdapter,
    FrozenClock,
    ConsensusEngine,
    ConsensusEngine,
    ConsensusEngine,
]:
    db = SQLiteAdapter(
        tmp_path / "consensus.db"
    )
    clock = FrozenClock()
    a = ConsensusEngine(
        db, clock, member_id="a"
    )
    b = ConsensusEngine(
        db, clock, member_id="b"
    )
    c = ConsensusEngine(
        db, clock, member_id="c"
    )
    a.register_member("a")
    a.register_member("b")
    a.register_member("c")
    return db, clock, a, b, c


def test_membership_and_quorum(
    tmp_path: Path,
) -> None:
    db, clock, a, b, c = _cluster(tmp_path)
    try:
        assert a.active_members() == (
            "a",
            "b",
            "c",
        )
        assert a.quorum_size() == 2
        a.deactivate_member("c")
        assert a.member_count() == 2
        assert a.quorum_size() == 2
    finally:
        db.close()


def test_vote_once_per_term(
    tmp_path: Path,
) -> None:
    db, clock, a, b, c = _cluster(tmp_path)
    try:
        term = a.start_new_term()
        assert term == 1
        a.vote(term=term, candidate_id="b")
        with pytest.raises(
            AlreadyVotedError
        ):
            a.vote(
                term=term,
                candidate_id="c",
            )
    finally:
        db.close()


def test_elect_leader_requires_quorum(
    tmp_path: Path,
) -> None:
    db, clock, a, b, c = _cluster(tmp_path)
    try:
        term = a.start_new_term()
        b.vote(term=term, candidate_id="c")
        with pytest.raises(
            ConsensusError
        ):
            c.elect_leader(term=term)
        a.vote(
            term=term, candidate_id="c"
        )
        assert (
            c.elect_leader(term=term)
            == "c"
        )
        assert c.leader() == "c"
    finally:
        db.close()


def test_new_term_fences_leases(
    tmp_path: Path,
) -> None:
    db, clock, a, b, c = _cluster(tmp_path)
    try:
        term1 = a.start_new_term()
        token = a.acquire_lease(
            resource="primary-lock",
            holder_id="a",
            lease_seconds=100.0,
        )
        assert token == term1
        with pytest.raises(
            LeaseHeldError
        ):
            b.acquire_lease(
                resource="primary-lock",
                holder_id="b",
                lease_seconds=100.0,
            )
        term2 = a.start_new_term()
        assert term2 == term1 + 1
        assert a.leader() is None
        held = a.lease_holder(
            "primary-lock"
        )
        assert held is not None
        with pytest.raises(NoLeaseError):
            a.renew_lease(
                resource="primary-lock",
                holder_id="a",
                lease_seconds=100.0,
            )
        fresh = b.acquire_lease(
            resource="primary-lock",
            holder_id="b",
            lease_seconds=100.0,
        )
        assert fresh == term2
        a.release_lease(
            resource="primary-lock",
            holder_id="b",
        )
        with pytest.raises(NoLeaseError):
            a.release_lease(
                resource="primary-lock",
                holder_id="b",
            )
    finally:
        db.close()

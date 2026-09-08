from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.hardening.api_keys import ApiKeyManager
from shared_engines.hardening.bruteforce import BruteForceGuard
from shared_engines.hardening.errors import (
    ApiKeyNotFoundError,
    ApiKeyRevokedError,
    InvalidApiKeyError,
    RateLimitExceededError,
    SourceLockedError,
)
from shared_engines.hardening.ratelimit import RateLimiter
from shared_engines.storage.database import SQLiteAdapter


class _Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.db = SQLiteAdapter(tmp_path / "hardening.db")
        self.clock = FrozenClock()
        self.audit = AuditTrail(self.db, self.clock)
        self.keys = ApiKeyManager(self.db, self.clock, self.audit)
        self.limiter = RateLimiter(self.db, self.clock)
        self.guard = BruteForceGuard(
            self.db,
            self.clock,
            max_failures=3,
            lockout_seconds=900,
        )

    def close(self) -> None:
        self.db.close()


def test_generate_and_verify_roundtrip(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    full_key, record = harness.keys.generate(
        label="nexo-app", created_by="founder"
    )
    assert full_key.startswith("zy_")
    verified = harness.keys.verify(full_key)
    assert verified.key_id == record.key_id
    assert verified.active is True
    assert verified.label == "nexo-app"
    harness.close()


def test_verify_rejects_wrong_and_malformed(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    full_key, _ = harness.keys.generate(
        label="a", created_by="x"
    )
    tampered = full_key[:-2] + "ff"
    with pytest.raises(InvalidApiKeyError):
        harness.keys.verify(tampered)
    with pytest.raises(InvalidApiKeyError):
        harness.keys.verify("not-a-key")
    with pytest.raises(InvalidApiKeyError):
        harness.keys.verify("zy_abc")
    harness.close()


def test_revoke_blocks_and_audit_captures(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    full_key, record = harness.keys.generate(
        label="subastas", created_by="founder"
    )
    harness.keys.revoke(record.key_id, revoked_by="admin")
    with pytest.raises(ApiKeyRevokedError):
        harness.keys.verify(full_key)
    assert harness.audit.verify() >= 2
    with pytest.raises(ApiKeyRevokedError):
        harness.keys.revoke(record.key_id, revoked_by="admin")
    harness.close()


def test_rotate_produces_new_working_key(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    old_key, old_record = harness.keys.generate(
        label="bank", created_by="founder"
    )
    new_key, new_record = harness.keys.rotate(
        old_record.key_id, rotated_by="admin"
    )
    assert new_record.key_id != old_record.key_id
    verified = harness.keys.verify(new_key)
    assert verified.active is True
    with pytest.raises(ApiKeyRevokedError):
        harness.keys.verify(old_key)
    assert "rotated" in new_record.label
    harness.close()


def test_stolen_database_yields_no_usable_keys(
    tmp_path: Path,
) -> None:
    """The database stores hashes only; a thief with full DB
    access cannot reconstruct any usable key."""
    harness = _Harness(tmp_path)
    harness.keys.generate(label="x", created_by="y")
    rows = harness.db.query_all("SELECT * FROM api_keys")
    for row in rows:
        stored = str(row["key_hash"])
        assert not stored.startswith("zy_")
        assert len(stored) == 64
    harness.close()


def test_rate_limit_allows_then_blocks(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    limiter = RateLimiter(
        harness.db, harness.clock, default_limit=3
    )
    for _ in range(3):
        result = limiter.check("key-1")
        assert result.allowed is True
    blocked = limiter.check("key-1")
    assert blocked.allowed is False
    with pytest.raises(RateLimitExceededError):
        limiter.enforce("key-1")
    harness.clock.advance(3600)
    recovered = limiter.check("key-1")
    assert recovered.allowed is True
    harness.close()


def test_rate_limit_per_key_independent(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    limiter = RateLimiter(
        harness.db, harness.clock, default_limit=2
    )
    limiter.enforce("key-a")
    limiter.enforce("key-a")
    with pytest.raises(RateLimitExceededError):
        limiter.enforce("key-a")
    result = limiter.enforce("key-b")
    assert result.allowed is True
    harness.close()


def test_bruteforce_locks_after_threshold(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    harness.guard.check_allowed("ip-1")
    assert harness.guard.record_failure("ip-1") is False
    assert harness.guard.record_failure("ip-1") is False
    assert harness.guard.record_failure("ip-1") is True
    with pytest.raises(SourceLockedError):
        harness.guard.check_allowed("ip-1")
    harness.close()


def test_bruteforce_unlocks_after_timeout(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    for _ in range(3):
        harness.guard.record_failure("ip-2")
    with pytest.raises(SourceLockedError):
        harness.guard.check_allowed("ip-2")
    harness.clock.advance(901)
    harness.guard.check_allowed("ip-2")
    assert harness.guard.record_failure("ip-2") is False
    harness.close()


def test_bruteforce_reset_on_success(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    harness.guard.record_failure("ip-3")
    harness.guard.record_failure("ip-3")
    harness.guard.reset("ip-3")
    assert harness.guard.record_failure("ip-3") is False
    harness.close()


def test_unknown_key_revoke(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    with pytest.raises(ApiKeyNotFoundError):
        harness.keys.revoke("nonexistent", revoked_by="admin")
    harness.close()


def test_audit_chain_intact_after_all_ops(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    _key1, r1 = harness.keys.generate(
        label="a", created_by="f"
    )
    harness.keys.generate(label="b", created_by="f")
    harness.keys.revoke(r1.key_id, revoked_by="admin")
    assert harness.audit.verify() >= 3
    assert len(harness.keys.list_active()) == 1
    assert harness.keys.list_active()[0].label == "b"
    harness.close()

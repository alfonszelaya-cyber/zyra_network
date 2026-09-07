from __future__ import annotations

import os
from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.common.errors import ConfigurationError, IntegrityError
from shared_engines.events.contracts import Event
from shared_engines.events.outbox import Outbox
from shared_engines.observability.backend import InMemoryMetrics
from shared_engines.observability.health import HealthStatus
from shared_engines.security.crypto import EnvelopeCrypto
from shared_engines.security.engine import SecurityEngine
from shared_engines.security.keys import (
    EnvironmentKeyProvider,
    StaticKeyProvider,
    crypto_from_provider,
)
from shared_engines.storage.database import SQLiteAdapter

KEY1 = os.urandom(32)
KEY2 = os.urandom(32)


def test_seal_open_roundtrip() -> None:
    crypto = EnvelopeCrypto({1: KEY1}, 1)
    sealed = crypto.seal(b"secret-payload", aad=b"context-1")
    assert crypto.open(sealed, aad=b"context-1") == b"secret-payload"


def test_tampered_ciphertext_rejected() -> None:
    crypto = EnvelopeCrypto({1: KEY1}, 1)
    sealed = crypto.seal(b"secret", aad=b"ctx")
    tampered = sealed[:-4] + b"AAAA"
    with pytest.raises(IntegrityError):
        crypto.open(tampered, aad=b"ctx")


def test_wrong_aad_rejected() -> None:
    crypto = EnvelopeCrypto({1: KEY1}, 1)
    sealed = crypto.seal(b"secret", aad=b"ctx-a")
    with pytest.raises(IntegrityError):
        crypto.open(sealed, aad=b"ctx-b")


def test_wrong_key_rejected() -> None:
    sealed = EnvelopeCrypto({1: KEY1}, 1).seal(b"secret", aad=b"ctx")
    other = EnvelopeCrypto({1: KEY2}, 1)
    with pytest.raises(IntegrityError):
        other.open(sealed, aad=b"ctx")


def test_rotation_keeps_history_and_reseal_upgrades() -> None:
    crypto = EnvelopeCrypto({1: KEY1}, 1)
    sealed_v1 = crypto.seal(b"secret", aad=b"ctx")
    assert crypto.inspect_key_version(sealed_v1) == 1
    crypto.rotate(2, KEY2)
    assert crypto.current_version == 2
    assert crypto.open(sealed_v1, aad=b"ctx") == b"secret"
    sealed_v2 = crypto.reseal(sealed_v1, aad=b"ctx")
    assert crypto.inspect_key_version(sealed_v2) == 2
    assert crypto.open(sealed_v2, aad=b"ctx") == b"secret"
    with pytest.raises(ConfigurationError):
        crypto.rotate(2, KEY2)


def test_key_providers() -> None:
    crypto = crypto_from_provider(StaticKeyProvider({1: KEY1}, 1))
    sealed = crypto.seal(b"x", aad=b"a")
    assert crypto.open(sealed, aad=b"a") == b"x"
    env = {
        "ZYRA_MASTER_KEY_V1": KEY1.hex(),
        "ZYRA_MASTER_KEY_V2": KEY2.hex(),
        "ZYRA_MASTER_KEY_CURRENT": "2",
    }
    from_env = crypto_from_provider(EnvironmentKeyProvider(env=env))
    assert from_env.current_version == 2
    bad_current = {
        "ZYRA_MASTER_KEY_V1": KEY1.hex(),
        "ZYRA_MASTER_KEY_CURRENT": "9",
    }
    with pytest.raises(ConfigurationError):
        crypto_from_provider(EnvironmentKeyProvider(env=bad_current))
    bad_hex = dict(env)
    bad_hex["ZYRA_MASTER_KEY_V3"] = "not-hex"
    with pytest.raises(ConfigurationError):
        crypto_from_provider(EnvironmentKeyProvider(env=bad_hex))


def test_security_engine_end_to_end(tmp_path: Path) -> None:
    db = SQLiteAdapter(tmp_path / "sec.db")
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    crypto = EnvelopeCrypto({1: KEY1}, 1)
    metrics = InMemoryMetrics()
    engine = SecurityEngine(
        crypto=crypto, audit=audit, db=db, clock=clock, metrics=metrics
    )
    sealed = engine.seal_record(b"payload-secret", context="vault-1")
    assert engine.open_record(sealed, context="vault-1") == b"payload-secret"
    with pytest.raises(IntegrityError):
        engine.open_record(sealed, context="vault-2")
    engine.rotate_key(2, KEY2)
    assert crypto.current_version == 2
    assert metrics.counter_value(
        "security.record.sealed", {"result": "ok"}
    ) == 1
    assert metrics.counter_value(
        "security.record.tamper_detected", {"context": "vault-2"}
    ) == 1
    assert metrics.counter_value(
        "security.key.rotated", {"key_version": "2"}
    ) == 1
    assert audit.verify() == 3
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    delivered: list[str] = []

    def collect(event: Event) -> None:
        delivered.append(event.event_type)

    assert outbox.dispatch_pending(collect) == 1
    assert delivered == ["security.key.rotated"]
    assert engine.check_health().status is HealthStatus.HEALTHY
    db.close()

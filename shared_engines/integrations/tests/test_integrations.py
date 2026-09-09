"""Integration proofs: transient retry succeeds,
permanent raises, budget exhausted (one failed
invocation recorded per invoke), unknown and
unwired refused."""
from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.common.errors import (
    ConfigurationError,
    ProviderPermanentError,
    ProviderTransientError,
)
from shared_engines.integrations.engine import (
    IntegrationsEngine,
    UnknownAdapterError,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)


def _engine(
    tmp_path: Path,
) -> IntegrationsEngine:
    db = SQLiteAdapter(
        tmp_path / "integ.db"
    )
    clock = FrozenClock()
    engine = IntegrationsEngine(db, clock)
    engine.register_adapter(
        adapter_id="kyc-provider",
        kind="http",
        endpoint="https://api.example",
        max_retries=3,
    )
    return engine


def test_transient_then_success(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    calls = {"n": 0}

    def flaky(payload: bytes) -> bytes:
        calls["n"] += 1
        if calls["n"] < 2:
            raise ProviderTransientError(
                "timeout"
            )
        return b"ok:" + payload

    engine.register_handler(
        adapter_id="kyc-provider",
        handler=flaky,
    )
    result = engine.invoke(
        adapter_id="kyc-provider",
        payload=b"doc",
    )
    assert result.attempts == 2
    health = engine.health(
        adapter_id="kyc-provider"
    )
    assert health.calls == 1
    assert health.failures == 0


def test_permanent_raises_and_counts(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)

    def broken(payload: bytes) -> bytes:
        raise ProviderPermanentError(
            "bad request"
        )

    engine.register_handler(
        adapter_id="kyc-provider",
        handler=broken,
    )
    with pytest.raises(
        ProviderPermanentError
    ):
        engine.invoke(
            adapter_id="kyc-provider",
            payload=b"x",
        )
    health = engine.health(
        adapter_id="kyc-provider"
    )
    assert health.failures == 1


def test_retry_budget_exhausted(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)

    def always_transient(
        payload: bytes,
    ) -> bytes:
        raise ProviderTransientError(
            "down"
        )

    engine.register_handler(
        adapter_id="kyc-provider",
        handler=always_transient,
    )
    with pytest.raises(
        ProviderPermanentError
    ):
        engine.invoke(
            adapter_id="kyc-provider",
            payload=b"x",
        )
    health = engine.health(
        adapter_id="kyc-provider"
    )
    # Contract: ONE failed invocation is
    # recorded per invoke() call, regardless
    # of internal retry attempts.
    assert health.calls == 1
    assert health.failures == 1


def test_unknown_and_unwired(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    with pytest.raises(UnknownAdapterError):
        engine.invoke(
            adapter_id="ghost",
            payload=b"x",
        )
    with pytest.raises(
        ConfigurationError
    ):
        engine.invoke(
            adapter_id="kyc-provider",
            payload=b"x",
        )

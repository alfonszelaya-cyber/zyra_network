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


def test_public_source_cache_and_stale(
    tmp_path: Path,
) -> None:
    """AX-SOURCES: cache TTL evita
    martillar la fuente; si cae,
    sirve cache con stale=True."""
    import hashlib
    from shared_engines.integrations.engine import (
        PublicSourceClient)

    class _Clock:
        def __init__(self):
            self.t = 1000.0

        def now(self):
            return self.t

    llamadas = {"n": 0}
    cuerpo = b'{"ok": true}'

    def opener(url: str) -> bytes:
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise OSError("down")
        return cuerpo

    ck = _Clock()
    cli = PublicSourceClient(
        clock=ck,
        ttl_seconds=60.0,
        opener=opener)
    b1, stale1 = cli.fetch(
        "https://fuente.gob/data")
    assert b1 == cuerpo
    assert stale1 is False
    b2, stale2 = cli.fetch(
        "https://fuente.gob/data")
    assert b2 == cuerpo
    assert stale2 is False
    assert llamadas["n"] == 1, (
        "cache no uso el TTL")
    ck.t = 1100.0
    b3, stale3 = cli.fetch(
        "https://fuente.gob/data")
    assert b3 == cuerpo
    assert stale3 is True
    assert hashlib.sha256(
        b3).hexdigest()


def test_source_adapters_via_engine(
    tmp_path: Path,
) -> None:
    """AX-SOURCES: fuente publica =
    adapter en IntegrationsEngine +
    handler con parser ligero."""
    import json
    from shared_engines.integrations.engine import (
        IntegrationsEngine,
        parse_geojson_summary)

    geojson = json.dumps({
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature"},
            {"type": "Feature"},
        ],
    }).encode("utf-8")

    engine = IntegrationsEngine(
        SQLiteAdapter(
            tmp_path / "src.db"),
        FrozenClock())
    engine.register_adapter(
        adapter_id="marn-geo",
        kind="http-geo",
        endpoint=(
            "https://geoportal"
            ".marn.gob/arcgis"),
        max_retries=2,
    )

    def marn_handler(
        payload: bytes,
    ) -> bytes:
        resumen = (
            parse_geojson_summary(
                geojson))
        return json.dumps(
            resumen).encode(
            "utf-8")

    engine.register_handler(
        adapter_id="marn-geo",
        handler=marn_handler,
    )
    result = engine.invoke(
        adapter_id="marn-geo",
        payload=b"query",
    )
    assert result.attempts == 1
    health = engine.health(
        adapter_id="marn-geo")
    assert health.calls == 1
    assert health.failures == 0


def test_parsers_lightweight(
    tmp_path: Path,
) -> None:
    """AX-SOURCES: parsers devuelven
    RESUMEN + sha256 (Red ligera)."""
    import json
    from shared_engines.integrations.engine import (
        parse_json_source,
        parse_cap_alerts)

    one = json.dumps([
        {"codigo": "011101"},
        {"codigo": "011102"},
    ]).encode("utf-8")
    r = parse_json_source(one)
    assert r["items"] == 2
    assert r["kind"] == "json"

    cap = (
        "<?xml version='1.0'?>"
        "<alert>"
        "<info><event>Lluvia"
        "</event><severity>Moderate"
        "</severity></info>"
        "<info><event>Sequia"
        "</event><severity>Severe"
        "</severity></info>"
        "</alert>"
    ).encode("utf-8")
    c = parse_cap_alerts(cap)
    assert c["count"] == 2
    assert c["alerts"][0][
        "event"] == "Lluvia"


def test_sweep_all_sources(
    tmp_path,
) -> None:
    """AX-SOURCES: barrido completo
    con fixtures - ONEC 7 endpoints,
    MARN descubrimiento de capas por
    servicio, snapshots durables en
    el indice."""
    import json
    from shared_engines.integrations.engine import (
        PublicSourceClient,
        SourceIndex,
        sweep_onec, sweep_marn,
        ONEC_ENDPOINTS,
        ARCGIS_SERVICES)
    from shared_engines.common.clocks import (
        FrozenClock)
    from shared_engines.storage.database import (
        SQLiteAdapter)

    geo = json.dumps({
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature"},
            {"type": "Feature"},
        ],
    }).encode("utf-8")
    meta = json.dumps({
        "layers": [
            {"id": 0,
             "name": "a"},
            {"id": 1,
             "name": "b"},
        ],
    }).encode("utf-8")
    one = json.dumps([
        {"codigo": "0111101"},
    ]).encode("utf-8")

    def opener(url: str) -> bytes:
        if url.endswith("?f=json"):
            return meta
        if ("/query" in url):
            return geo
        if url.endswith(tuple(
            ONEC_ENDPOINTS
        )):
            return one
        raise OSError("no simulada")

    cli = PublicSourceClient(
        clock=FrozenClock(),
        ttl_seconds=60.0,
        opener=opener)
    index = SourceIndex(
        SQLiteAdapter(
            tmp_path / "src.db"),
        FrozenClock())
    r1 = sweep_onec(cli, index)
    assert r1["ok"] == 7
    assert r1["total"] == 7
    r2 = sweep_marn(
        cli, index,
        max_layers_per_service=2,
        pause_seconds=0)
    assert r2["layers_total"] == (
        2 * len(ARCGIS_SERVICES[
            "marn-geo"]))
    assert r2["layers_ok"] == (
        r2["layers_total"])
    rows = index._db.query_all(
        "SELECT * FROM"
        " source_snapshots")
    assert len(rows) == (7 + 2
        * len(ARCGIS_SERVICES[
            "marn-geo"]))
    print("OK barrido completo:"
          " 7 ONEC + "
          + str(r2["layers_total"])
          + " capas MARN +"
          " snapshots durables")

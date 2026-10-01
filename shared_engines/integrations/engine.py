"""Integrations engine: external adapters with
retry, health and durable stats. Real providers
are wired as handler callables at the composition
root; the engine governs invocation: bounded
retries on transient failures, durable counters,
health. No fake providers live here."""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import (
    ConfigurationError,
    IntegrityError,
    NotFoundError,
    ProviderPermanentError,
    ProviderTransientError,
)
from shared_engines.common.validation import (
    require_int_range,
    require_non_empty_str,
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
        "integrations",
        (
            "CREATE TABLE"
            " integration_adapters ("
            " adapter_id TEXT PRIMARY"
            " KEY,"
            " kind TEXT NOT NULL,"
            " endpoint TEXT NOT NULL,"
            " max_retries INTEGER NOT"
            " NULL,"
            " calls INTEGER NOT NULL"
            " DEFAULT 0,"
            " failures INTEGER NOT NULL"
            " DEFAULT 0,"
            " created_at REAL NOT NULL)",
        ),
    ),
)


class UnknownAdapterError(NotFoundError):
    """Adapter not registered."""


@dataclass(frozen=True)
class AdapterRecord:
    adapter_id: str
    kind: str
    endpoint: str
    max_retries: int
    calls: int
    failures: int


@dataclass(frozen=True)
class InvokeResult:
    adapter_id: str
    attempts: int
    response_sha256: str


class IntegrationsEngine:
    """Governed invocation of external
    adapters."""

    def __init__(
        self, db: Database, clock: Clock
    ) -> None:
        self._db = db
        self._clock = clock
        self._handlers: dict[
            str,
            Callable[[bytes], bytes],
        ] = {}
        MigrationRunner(
            db,
            "integrations",
            _MIGRATIONS,
        ).run(clock)

    def register_adapter(
        self,
        *,
        adapter_id: str,
        kind: str,
        endpoint: str,
        max_retries: int = 3,
    ) -> AdapterRecord:
        require_non_empty_str(
            adapter_id, "adapter_id"
        )
        require_non_empty_str(
            kind, "kind"
        )
        require_non_empty_str(
            endpoint, "endpoint"
        )
        require_int_range(
            max_retries,
            "max_retries",
            1,
            10,
        )
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO"
                " integration_adapters"
                " (adapter_id, kind,"
                "  endpoint, max_retries,"
                "  calls, failures,"
                "  created_at)"
                " VALUES (?, ?, ?, ?, 0, 0,"
                " ?)"
                " ON CONFLICT(adapter_id)"
                " DO UPDATE SET kind ="
                " excluded.kind, endpoint"
                " = excluded.endpoint,"
                " max_retries ="
                " excluded.max_retries",
                (
                    adapter_id,
                    kind,
                    endpoint,
                    max_retries,
                    self._clock.now(),
                ),
            )
        return self.health(
            adapter_id=adapter_id
        )

    def register_handler(
        self,
        *,
        adapter_id: str,
        handler: Callable[[bytes], bytes],
    ) -> None:
        require_non_empty_str(
            adapter_id, "adapter_id"
        )
        self._row(adapter_id)
        self._handlers[adapter_id] = (
            handler
        )

    def _row(
        self, adapter_id: str
    ) -> AdapterRecord:
        row = self._db.query_one(
            "SELECT * FROM"
            " integration_adapters"
            " WHERE adapter_id = ?",
            (adapter_id,),
        )
        if row is None:
            raise UnknownAdapterError(
                "unknown adapter:"
                f" {adapter_id}"
            )
        return AdapterRecord(
            adapter_id=str(
                row["adapter_id"]
            ),
            kind=str(row["kind"]),
            endpoint=str(
                row["endpoint"]
            ),
            max_retries=int(
                row["max_retries"]
            ),
            calls=int(row["calls"]),
            failures=int(
                row["failures"]
            ),
        )

    def invoke(
        self,
        *,
        adapter_id: str,
        payload: bytes,
    ) -> InvokeResult:
        require_non_empty_str(
            adapter_id, "adapter_id"
        )
        if not payload:
            raise IntegrityError(
                "payload required"
            )
        record = self._row(adapter_id)
        handler = self._handlers.get(
            adapter_id
        )
        if handler is None:
            raise ConfigurationError(
                "no handler wired for"
                f" '{adapter_id}'"
            )
        attempts = 0
        last_exc: Exception | None = (
            None
        )
        while attempts < (
            record.max_retries
        ):
            attempts += 1
            try:
                response = handler(
                    payload
                )
                self._bump(
                    adapter_id,
                    failure=False,
                )
                return InvokeResult(
                    adapter_id=(
                        adapter_id
                    ),
                    attempts=attempts,
                    response_sha256=hashlib.sha256(
                        response
                    ).hexdigest(),
                )
            except (
                ProviderTransientError
            ) as exc:
                last_exc = exc
            except (
                ProviderPermanentError
            ):
                self._bump(
                    adapter_id,
                    failure=True,
                )
                raise
        self._bump(
            adapter_id, failure=True
        )
        raise ProviderPermanentError(
            "adapter"
            f" '{adapter_id}' failed"
            f" after {attempts}"
            f" attempts: {last_exc}"
        ) from last_exc

    def _bump(
        self,
        adapter_id: str,
        *,
        failure: bool,
    ) -> None:
        delta_fail = 1 if failure else 0
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "UPDATE"
                " integration_adapters"
                " SET calls = calls + 1,"
                " failures = failures"
                " + ?"
                " WHERE adapter_id = ?",
                (delta_fail, adapter_id),
            )

    def health(
        self, *, adapter_id: str
    ) -> AdapterRecord:
        return self._row(adapter_id)

class PublicSourceClient:
    """AX-SOURCES: fetcher de
    fuentes publicas con cache TTL
    en memoria. La Red nunca
    martilla a la fuente; si cae,
    sirve cache con stale=True.
    La Red transporta confianza,
    no carga."""

    def __init__(
        self,
        *,
        clock: Clock,
        timeout_seconds: float = (
            15.0),
        ttl_seconds: float = (
            300.0),
        opener: Callable[
            [str], bytes] | None = (
            None),
    ) -> None:
        self._clock = clock
        self._timeout = (
            timeout_seconds)
        self._ttl = ttl_seconds
        self._opener = (
            opener
            if opener is not None
            else self._urlopen)
        self._cache: dict[
            str,
            tuple[float, bytes],
        ] = {}

    def _urlopen(
        self, url: str,
    ) -> bytes:
        import urllib.request
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent":
                "zyra-network/1.0"
            },
        )
        with urllib.request.urlopen(
            req,
            timeout=self._timeout,
        ) as r:
            return r.read()

    def fetch(
        self, url: str,
    ) -> tuple[bytes, bool]:
        """Devuelve (body, stale)."""
        now = self._clock.now()
        hit = self._cache.get(url)
        if hit is not None:
            ts, body = hit
            if (now - ts) < (
                    self._ttl):
                return (
                    body, False)
        try:
            body = self._opener(
                url)
        except Exception:
            if hit is not None:
                return (
                    hit[1], True)
            raise
        self._cache[url] = (
            now, body)
        return body, False


def parse_geojson_summary(
    body: bytes,
) -> dict[str, object]:
    """Resumen ligero de capa
    ArcGIS/GeoJSON."""
    import hashlib
    import json
    data = json.loads(
        body.decode("utf-8"))
    if data.get("type") not in (
        "FeatureCollection",
        "Feature",
    ):
        raise ValueError(
            "expected GeoJSON")
    features = data.get(
        "features", [])
    if data.get("type") == (
        "Feature"
    ):
        features = [data]
    return {
        "kind": "geojson",
        "features": len(features),
        "sha256": hashlib.sha256(
            body).hexdigest(),
    }


def parse_json_source(
    body: bytes,
) -> dict[str, object]:
    """Resumen de fuente JSON
    publica (ONEC etc.)."""
    import hashlib
    import json
    data = json.loads(
        body.decode("utf-8"))
    if isinstance(data, list):
        return {
            "kind": "json",
            "items": len(data),
            "sha256": hashlib.sha256(
                body).hexdigest(),
        }
    if isinstance(data, dict):
        return {
            "kind": "json",
            "keys": sorted(
                str(k) for k in
                data.keys())[:12],
            "sha256": hashlib.sha256(
                body).hexdigest(),
        }
    raise ValueError(
        "unexpected json shape")


def parse_cap_alerts(
    body: bytes,
) -> dict[str, object]:
    """Resumen de alertas CAP
    (XML de Proteccion Civil)."""
    import hashlib
    import xml.etree.ElementTree as ET
    root = ET.fromstring(body)
    parts = root.tag.split("}")
    ns = (parts[0][1:]
          if len(parts) == 2
          else "")
    q = (lambda tag:
         ((ns + tag) if ns
          else tag))
    alerts = []
    for info in root.iter(
        q("info")
    ):
        ev = info.find(q("event"))
        sev = info.find(
            q("severity"))
        alerts.append({
            "event": (
                ev.text
                if ev is not None
                else ""),
            "severity": (
                sev.text
                if sev is not None
                else ""),
        })
    return {
        "kind": "cap",
        "alerts": alerts[:20],
        "count": len(alerts),
        "sha256": hashlib.sha256(
            body).hexdigest(),
    }

"""Security engine: sealed records, security events, rotation.

Every path exercises real infrastructure: writes go through
the audit hash chain, rotation publishes through the
transactional outbox, counters go through the metrics backend.
No secrets or plaintext are ever logged.
"""
from __future__ import annotations

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.errors import IntegrityError
from shared_engines.common.validation import require_non_empty_str
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.observability.backend import (
    MetricsBackend,
    NoopMetrics,
    engine_logger,
)
from shared_engines.observability.health import (
    ComponentHealth,
    HealthStatus,
)
from shared_engines.security.crypto import EnvelopeCrypto
from shared_engines.storage.database import Database

SECURITY_EVENT_TYPES = (
    "security.record.sealed",
    "security.record.tamper_detected",
    "security.key.rotated",
)


def register_security_events(catalog: EventCatalog) -> None:
    for event_type in SECURITY_EVENT_TYPES:
        catalog.register(event_type)


class SecurityEngine:
    def __init__(
        self,
        *,
        crypto: EnvelopeCrypto,
        audit: AuditTrail,
        db: Database,
        clock: Clock,
        metrics: MetricsBackend | None = None,
    ) -> None:
        self._crypto = crypto
        self._audit = audit
        self._clock = clock
        self._metrics = metrics if metrics is not None else NoopMetrics()
        self._log = engine_logger("security")
        self._catalog = EventCatalog()
        register_security_events(self._catalog)
        self._outbox = Outbox(db, self._clock)
        self._outbox.ensure_schema()

    def _aad(self, context: str) -> bytes:
        return f"security-record:{context}".encode("utf-8")

    def seal_record(self, plaintext: bytes, *, context: str) -> str:
        require_non_empty_str(context, "context")
        sealed = self._crypto.seal(plaintext, aad=self._aad(context))
        self._audit.append(
            event_type="security.record.sealed",
            actor="security-engine",
            subject=context,
            payload={"key_version": self._crypto.current_version},
        )
        self._metrics.increment(
            "security.record.sealed", tags={"result": "ok"}
        )
        self._log.info(
            "sealed record subject=%s key_version=%d",
            context,
            self._crypto.current_version,
        )
        return sealed.decode("utf-8")

    def open_record(self, sealed: str, *, context: str) -> bytes:
        require_non_empty_str(context, "context")
        try:
            return self._crypto.open(
                sealed.encode("utf-8"), aad=self._aad(context)
            )
        except IntegrityError:
            self._audit.append(
                event_type="security.record.tamper_detected",
                actor="security-engine",
                subject=context,
                payload={},
            )
            self._metrics.increment(
                "security.record.tamper_detected",
                tags={"context": context},
            )
            self._log.warning(
                "tamper detected on record subject=%s", context
            )
            raise

    def rotate_key(self, new_version: int, new_key: bytes) -> None:
        self._crypto.rotate(new_version, new_key)
        self._audit.append(
            event_type="security.key.rotated",
            actor="security-engine",
            subject=f"key-v{new_version}",
            payload={"key_version": new_version},
        )
        event = self._catalog.build(
            "security.key.rotated",
            aggregate_id=f"key-v{new_version}",
            payload={"key_version": new_version},
            clock=self._clock,
        )
        self._outbox.enqueue(event)
        self._metrics.increment(
            "security.key.rotated",
            tags={"key_version": str(new_version)},
        )
        self._log.info("rotated key to version=%d", new_version)

    def check_health(self) -> ComponentHealth:
        try:
            probe = b"healthcheck"
            sealed = self._crypto.seal(probe, aad=b"healthcheck-probe")
            ok = self._crypto.open(
                sealed, aad=b"healthcheck-probe"
            ) == probe
        except Exception:
            return ComponentHealth(
                "security",
                HealthStatus.UNHEALTHY,
                "crypto self-test failed",
            )
        status = HealthStatus.HEALTHY if ok else HealthStatus.UNHEALTHY
        return ComponentHealth("security", status, "crypto self-test")

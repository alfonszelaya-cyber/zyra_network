"""Identity engine: the public facade of the capability.

Apps and other engines talk to this object only; storage,
events and audit stay behind it.
"""
from __future__ import annotations

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import (
    Identity,
    IdentityKind,
    IdentityStatus,
)
from shared_engines.identity.registry import (
    IdentityRegistry,
    RegistryPage,
)
from shared_engines.observability.backend import (
    MetricsBackend,
    NoopMetrics,
    engine_logger,
)
from shared_engines.observability.health import (
    ComponentHealth,
    HealthStatus,
)
from shared_engines.storage.database import Database


class IdentityEngine:
    def __init__(
        self,
        *,
        db: Database,
        clock: Clock,
        audit: AuditTrail,
        outbox: Outbox,
        catalog: EventCatalog,
        metrics: MetricsBackend | None = None,
    ) -> None:
        self._registry = IdentityRegistry(
            db=db,
            clock=clock,
            audit=audit,
            outbox=outbox,
            catalog=catalog,
        )
        self._db = db
        self._metrics = metrics if metrics is not None else NoopMetrics()
        self._log = engine_logger("identity")

    def register_identity(
        self, *, kind: IdentityKind, display_name: str, actor: str
    ) -> Identity:
        identity = self._registry.create(
            kind=kind, display_name=display_name, actor=actor
        )
        self._metrics.increment(
            "identity.registered", tags={"kind": kind.value}
        )
        self._log.info(
            "registered zid=%s kind=%s", identity.zid, kind.value
        )
        return identity

    def get_identity(self, zid: str) -> Identity | None:
        return self._registry.get(zid)

    def require_identity(self, zid: str) -> Identity:
        return self._registry.require(zid)

    def transition_identity(
        self,
        zid: str,
        to_status: IdentityStatus,
        *,
        actor: str,
        reason: str,
    ) -> Identity:
        identity = self._registry.transition(
            zid, to_status, actor=actor, reason=reason
        )
        self._metrics.increment(
            "identity.transition", tags={"to": to_status.value}
        )
        self._log.info(
            "transition zid=%s to=%s", zid, to_status.value
        )
        return identity

    def list_by_status(
        self,
        status: IdentityStatus,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> RegistryPage:
        return self._registry.list_by_status(
            status, offset=offset, limit=limit
        )

    def check_health(self) -> ComponentHealth:
        if not self._db.ping():
            return ComponentHealth(
                "identity",
                HealthStatus.UNHEALTHY,
                "storage unavailable",
            )
        return ComponentHealth(
            "identity", HealthStatus.HEALTHY, "storage ok"
        )

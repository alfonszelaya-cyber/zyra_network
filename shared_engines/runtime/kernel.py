"""ZyraKernel: the living composition root of the Network.

Builds and owns every engine over one durable database,
registers a central event catalog, bootstraps the Root
Authority identity (the Network's own ACTIVE institution),
and aggregates component health. This is the object the
HTTP layer serves; nothing else needs to know the wiring.
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
from shared_engines.identity.engine import IdentityEngine
from shared_engines.observability.backend import (
    MetricsBackend,
    NoopMetrics,
    engine_logger,
)
from shared_engines.observability.health import (
    ComponentHealth,
    HealthRegistry,
    HealthStatus,
)
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.storage.database import Database
from shared_engines.verification.engine import VerificationEngine
from shared_engines.verification.signatures import Ed25519Signer

NETWORK_EVENT_TYPES = (
    "identity.registered",
    "identity.status_changed",
    "verification.media.registered",
    "verification.media.tamper_detected",
    "verification.credential.issued",
    "verification.credential.revoked",
    "verification.attestation.issued",
)


class _StorageHealth:
    """Reports storage liveness through the adapter's ping."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def check_health(self) -> ComponentHealth:
        if self._db.ping():
            return ComponentHealth(
                "storage", HealthStatus.HEALTHY, "ping ok"
            )
        return ComponentHealth(
            "storage", HealthStatus.UNHEALTHY, "ping failed"
        )


class ZyraKernel:
    """Owns the engines; serves as the single source of truth."""

    def __init__(
        self,
        *,
        db: Database,
        clock: Clock,
        signer: Ed25519Signer,
        config: RuntimeConfig,
        metrics: MetricsBackend | None = None,
    ) -> None:
        self._config = config
        self._clock = clock
        self._db = db
        self._metrics = metrics if metrics is not None else NoopMetrics()
        self._log = engine_logger("runtime")
        self._audit = AuditTrail(db, clock)
        self._outbox = Outbox(db, clock)
        self._outbox.ensure_schema()
        self._catalog = EventCatalog()
        for event_type in NETWORK_EVENT_TYPES:
            self._catalog.register(event_type)
        self._identity = IdentityEngine(
            db=db,
            clock=clock,
            audit=self._audit,
            outbox=self._outbox,
            catalog=self._catalog,
            metrics=self._metrics,
        )
        self._verification = VerificationEngine(
            db=db,
            clock=clock,
            signer=signer,
            audit=self._audit,
            outbox=self._outbox,
            catalog=self._catalog,
            identity=self._identity,
            metrics=self._metrics,
        )
        self._health = HealthRegistry()
        self._health.register("storage", _StorageHealth(db))
        self._health.register("identity", self._identity)
        self._health.register("verification", self._verification)
        self._root_zid: str | None = None

    @property
    def config(self) -> RuntimeConfig:
        return self._config

    @property
    def identity(self) -> IdentityEngine:
        return self._identity

    @property
    def verification(self) -> VerificationEngine:
        return self._verification

    @property
    def audit(self) -> AuditTrail:
        return self._audit

    @property
    def outbox(self) -> Outbox:
        return self._outbox

    @property
    def root_zid(self) -> str | None:
        return self._root_zid

    def bootstrap_root(
        self, *, display_name: str = "Zyra Root Authority"
    ) -> Identity:
        """Creates/returns the Network's own ACTIVE authority.

        Idempotent: the first call registers + activates it;
        later calls return the same identity.
        """
        if self._root_zid is not None:
            return self._identity.require_identity(self._root_zid)
        root = self._identity.register_identity(
            kind=IdentityKind.INSTITUTION,
            display_name=display_name,
            actor="kernel",
        )
        self._identity.transition_identity(
            root.zid,
            IdentityStatus.ACTIVE,
            actor="kernel",
            reason="root authority bootstrap",
        )
        self._root_zid = root.zid
        self._log.info(
            "root authority bootstrapped zid=%s", root.zid
        )
        return self._identity.require_identity(root.zid)

    def health(self) -> ComponentHealth:
        """Worst-status aggregate across all components."""
        return self._health.overall()

    def health_components(self) -> tuple[ComponentHealth, ...]:
        return self._health.snapshot()

    def check_health(self) -> ComponentHealth:
        """Kernel itself satisfies the HealthCheck protocol."""
        return self.health()

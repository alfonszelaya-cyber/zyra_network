"""ZyraKernel: the living composition root of the Network.

Builds and owns every engine over one durable database,
registers the central event catalog, bootstraps the Root
Authority identity, wires the token ledger and the FX
engine, and aggregates component health.

Strengthening (additive only): wires the biometric
identity-proofing engine from
shared_engines/security/biometrics.py as a native engine,
sealed with keys derived from ZYRA_ROOT_KEY. Every
pre-existing engine and wiring line is unchanged; the
biometrics engine is an addition and is fail-closed until
the real face provider is installed.
"""
from __future__ import annotations

import os

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.currency.engine import CurrencyEngine
from shared_engines.currency.rates import StaticTableRateProvider
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
from shared_engines.security.biometrics import (
    BiometricsEngine,
    BiometricsPolicy,
    TemplateCipher,
    TemplateVector,
)
from shared_engines.storage.database import Database
from shared_engines.tokenization.engine import TokenEngine
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

DEFAULT_FX_RATES: dict[str, str] = {
    "USD/EUR": "0.92",
    "USD/CNY": "7.25",
    "GTQ/USD": "0.128",
    "USD/MXN": "17.0",
}


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


class _BiometricsHealth:
    """Reports biometric proofing availability."""

    def __init__(
        self, engine: BiometricsEngine | None
    ) -> None:
        self._engine = engine

    def check_health(self) -> ComponentHealth:
        if self._engine is not None:
            return ComponentHealth(
                "biometrics",
                HealthStatus.HEALTHY,
                "engine wired",
            )
        return ComponentHealth(
            "biometrics",
            HealthStatus.UNHEALTHY,
            "engine not configured",
        )


class _FailClosedProvider:
    """Fail-closed biometric provider.

    Default until the real face engine is installed.
    Refuses every extraction, so the network can
    NEVER approve an identity it did not truly
    analyze. The real provider plugs in via
    ZYRA_BIOMETRICS_PROVIDER later without changing
    this wiring.
    """

    name = "fail-closed"
    modality = "face"
    liveness_supported = False

    def extract_template(
        self, image: bytes
    ) -> TemplateVector:
        from shared_engines.security.biometrics import (
            ProviderError,
        )

        raise ProviderError(
            "real face engine not installed;"
            " biometric extraction refused"
        )

    def compare(
        self,
        a: TemplateVector,
        b: TemplateVector,
    ) -> float:
        from shared_engines.security.biometrics import (
            ProviderError,
        )

        raise ProviderError(
            "real face engine not installed;"
            " comparison refused"
        )

    def check_liveness(self, image: bytes) -> bool:
        return False


def _make_biometric_provider() -> object:
    """Provider selection by environment.

    ZYRA_BIOMETRICS_PROVIDER=fail-closed (default).
    'insightface' will plug in via
    shared_engines.security.biometrics_face in a later
    batch; any failure selecting it falls back to
    fail-closed. Never open.
    """
    choice = (
        os.environ.get(
            "ZYRA_BIOMETRICS_PROVIDER",
            "fail-closed",
        )
        .strip()
        .lower()
    )
    if choice == "insightface":
        try:
            from shared_engines.security.biometrics_face import (  # noqa: F401
                InsightFaceProvider,
            )

            return InsightFaceProvider()
        except Exception:
            return _FailClosedProvider()
    return _FailClosedProvider()


class ZyraKernel:
    """Owns the engines; serves as the single source of truth."""

    def __init__(
        self,
        *,
        db: Database,
        clock: Clock,
        signer: Ed25519Signer,
        config: RuntimeConfig,
        fx_rates: dict[str, str] | None = None,
        metrics: MetricsBackend | None = None,
        master_key_hex: str | None = None,
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
        self._tokens = TokenEngine(
            db=db,
            clock=clock,
            audit=self._audit,
            outbox=self._outbox,
            catalog=self._catalog,
            identity=self._identity,
            metrics=self._metrics,
        )
        self._currency = CurrencyEngine(
            db=db,
            clock=clock,
            providers=[
                StaticTableRateProvider(
                    fx_rates
                    if fx_rates is not None
                    else DEFAULT_FX_RATES,
                    clock,
                )
            ],
            signer=signer,
            audit=self._audit,
            outbox=self._outbox,
            catalog=self._catalog,
            identity=self._identity,
            metrics=self._metrics,
        )
        # --- biometric identity proofing (additive) ---
        self._biometrics: BiometricsEngine | None = None
        master_hex = (
            master_key_hex
            if master_key_hex is not None
            else os.environ.get("ZYRA_ROOT_KEY")
        )
        if master_hex:
            try:
                self._biometrics = BiometricsEngine(
                    db=db,
                    clock=clock,
                    audit=self._audit,
                    provider=_make_biometric_provider(),
                    cipher=TemplateCipher(
                        master_key_hex=master_hex
                    ),
                    policy=BiometricsPolicy(
                        require_liveness=True
                    ),
                    metrics=self._metrics,
                )
                self._log.info(
                    "biometrics engine wired"
                    " (fail-closed provider"
                    " until face model installed)"
                )
            except Exception as exc:
                self._log.error(
                    "biometrics engine init"
                    " failed: %s",
                    exc,
                )
                self._biometrics = None
        else:
            self._log.warning(
                "biometrics disabled: no master"
                " key available"
            )
        self._health = HealthRegistry()
        self._health.register("storage", _StorageHealth(db))
        self._health.register("identity", self._identity)
        self._health.register("verification", self._verification)
        self._health.register("tokens", self._tokens)
        self._health.register("currency", self._currency)
        self._health.register(
            "biometrics",
            _BiometricsHealth(self._biometrics),
        )
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
    def tokens(self) -> TokenEngine:
        return self._tokens

    @property
    def currency(self) -> CurrencyEngine:
        return self._currency

    @property
    def biometrics(self) -> BiometricsEngine | None:
        return self._biometrics

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
        """Creates/returns the Network's own ACTIVE authority."""
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

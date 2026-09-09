"""ZyraCapabilities: the trust-services composition
layer.

Composes the transverse engines into the
consumer-facing services of the Network, over one
durable database. Deliberately does NOT replace
ZyraKernel (which owns identity/verification/
tokens/currency): capabilities layers the trust
services on top, sharing the same database.
Engines whose wiring is a per-node decision
(consensus member_id, integrations handlers,
system_loader contract version) stay direct-use.
"""
from __future__ import annotations

from shared_engines.ai.engine import AIEngine
from shared_engines.audit.chain import AuditTrail
from shared_engines.certification.engine import (
    CertificationEngine,
)
from shared_engines.certification.registry import (
    IssuerRegistry,
)
from shared_engines.common.clocks import Clock
from shared_engines.compliance.engine import (
    ComplianceEngine,
)
from shared_engines.encryption.engine import (
    EncryptionEngine,
)
from shared_engines.events.contracts import (
    EventCatalog,
)
from shared_engines.events.outbox import Outbox
from shared_engines.export.engine import ExportEngine
from shared_engines.identity.engine import IdentityEngine
from shared_engines.integrity.engine import IntegrityEngine
from shared_engines.interoperability.engine import (
    InteroperabilityEngine,
)
from shared_engines.network.document_exchange import (
    DocumentExchange,
)
from shared_engines.network.life_history import LifeHistory
from shared_engines.network.portable_profile import (
    ProfileRegistry,
)
from shared_engines.network.trust_flow import TrustFlow
from shared_engines.reputation.engine import ReputationEngine
from shared_engines.search.engine import SearchEngine
from shared_engines.storage.database import Database
from shared_engines.verification.credentials import (
    CredentialRegistry,
)
from shared_engines.verification.signatures import (
    Ed25519Signer,
)

CAPABILITY_EVENT_TYPES = (
    "identity.registered",
    "identity.status_changed",
    "verification.credential.issued",
    "verification.credential.revoked",
    "network.profile.updated",
    "network.profile.accessed",
    "network.history.appended",
    "network.document.sealed",
    "network.signature.requested",
    "network.document.signed",
    "network.document.rejected",
    "network.search.performed",
    "reputation.event.recorded",
    "certification.certificate.issued",
    "certification.certificate.revoked",
    "compliance.decision.recorded",
    "export.bundle.created",
    "ai.analysis.recorded",
)


class ZyraCapabilities:
    """Trust services over one database."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        identity: IdentityEngine,
        signer: Ed25519Signer,
    ) -> None:
        self._db = db
        self._clock = clock
        self.audit = AuditTrail(db, clock)
        self.outbox = Outbox(db, clock)
        self.outbox.ensure_schema()
        self.catalog = EventCatalog()
        for event_type in (
            CAPABILITY_EVENT_TYPES
        ):
            self.catalog.register(event_type)
        self.profiles = ProfileRegistry(
            db,
            clock,
            audit=self.audit,
            outbox=self.outbox,
        )
        self.integrity = IntegrityEngine(
            db, clock
        )
        self.trust = TrustFlow(
            identity=identity,
            profiles=self.profiles,
        )
        self.history = LifeHistory(
            db,
            clock,
            audit=self.audit,
            outbox=self.outbox,
        )
        self.exchange = DocumentExchange(
            db,
            clock,
            signer=signer,
            integrity=self.integrity,
            audit=self.audit,
            outbox=self.outbox,
        )
        self.credentials = CredentialRegistry(
            db,
            clock,
            self.audit,
            self.outbox,
            self.catalog,
        )
        self.issuers = IssuerRegistry(db, clock)
        self.certification = CertificationEngine(
            db,
            clock,
            issuers=self.issuers,
            identity=identity,
            credentials=self.credentials,
            signer=signer,
            audit=self.audit,
            outbox=self.outbox,
        )
        self.search = SearchEngine(
            db,
            clock,
            audit=self.audit,
            outbox=self.outbox,
        )
        self.reputation = ReputationEngine(
            db,
            clock,
            identity=identity,
            integrity=self.integrity,
            audit=self.audit,
            outbox=self.outbox,
        )
        self.export = ExportEngine(
            db,
            clock,
            signer=signer,
            audit=self.audit,
        )
        self.interop = InteroperabilityEngine(
            db, clock
        )
        self.compliance = ComplianceEngine(
            db,
            clock,
            audit=self.audit,
            outbox=self.outbox,
        )
        self.ai = AIEngine(
            db,
            clock,
            audit=self.audit,
            outbox=self.outbox,
        )
        self.encryption = EncryptionEngine(
            db,
            clock,
            namespace="capabilities",
        )

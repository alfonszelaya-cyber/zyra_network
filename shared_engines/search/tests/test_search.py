"""Search proofs: multi-source ranked results,
unauthorized apps refused, pagination via Page,
full auditability of every query."""
from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.events.contracts import (
    EventCatalog,
)
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import (
    IdentityKind,
)
from shared_engines.identity.engine import (
    IdentityEngine,
)
from shared_engines.integrity.engine import (
    IntegrityEngine,
)
from shared_engines.network.document_exchange import (
    DocumentExchange,
)
from shared_engines.network.life_history import (
    LifeHistory,
)
from shared_engines.network.portable_profile import (
    ProfileRegistry,
)
from shared_engines.search.engine import SearchEngine
from shared_engines.search.errors import (
    SearchNotAuthorizedError,
    UnknownSourceError,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)
from shared_engines.telemetry.collector import (
    TelemetryCollector,
)
from shared_engines.verification.credentials import (
    CredentialRegistry,
    CredentialType,
)
from shared_engines.verification.signatures import (
    Ed25519Signer,
)


class _Net:
    def __init__(
        self, tmp_path: Path
    ) -> None:
        self.db = SQLiteAdapter(
            tmp_path / "net.db"
        )
        self.clock = FrozenClock()
        self.audit = AuditTrail(
            self.db, self.clock
        )
        self.outbox = Outbox(
            self.db, self.clock
        )
        self.outbox.ensure_schema()
        self.catalog = EventCatalog()
        for et in (
            "identity.registered",
            "identity.status_changed",
            "verification.credential"
            ".issued",
            "network.document.sealed",
            "network.history.appended",
            "network.search.performed",
        ):
            self.catalog.register(et)
        self.identity = IdentityEngine(
            db=self.db,
            clock=self.clock,
            audit=self.audit,
            outbox=self.outbox,
            catalog=self.catalog,
        )
        self.profiles = ProfileRegistry(
            self.db,
            self.clock,
            audit=self.audit,
            outbox=self.outbox,
        )
        self.credentials = (
            CredentialRegistry(
                self.db,
                self.clock,
                self.audit,
                self.outbox,
                self.catalog,
            )
        )
        self.integrity = IntegrityEngine(
            self.db, self.clock
        )
        signer, _ = (
            Ed25519Signer.generate()
        )
        self.exchange = DocumentExchange(
            self.db,
            self.clock,
            signer=signer,
            integrity=self.integrity,
            audit=self.audit,
            outbox=self.outbox,
        )
        self.history = LifeHistory(
            self.db,
            self.clock,
            audit=self.audit,
            outbox=self.outbox,
        )
        self.telemetry = TelemetryCollector(
            self.db, self.clock
        )
        self.search = SearchEngine(
            self.db,
            self.clock,
            audit=self.audit,
            outbox=self.outbox,
        )

    def close(self) -> None:
        self.db.close()


def test_multi_source_ranked_results(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="portal",
            display_name="Portal",
            scopes=("display_name",),
        )
        person = (
            net.identity.register_identity(
                kind=(
                    IdentityKind.PERSON
                ),
                display_name=(
                    "Maria Lopez"
                ),
                actor="portal",
            )
        )
        net.credentials.issue(
            subject_zid=person.zid,
            issuer_zid=person.zid,
            credential_type=(
                CredentialType.REFERENCE
            ),
            title=(
                "Referencia de"
                " Maria Lopez"
            ),
            detail="limpia",
        )
        net.exchange.seal_document(
            owner_zid=person.zid,
            title=(
                "Contrato Maria Lopez"
            ),
            content=b"doc",
            actor_app="portal",
        )
        result = net.search.search(
            app_id="portal",
            query="maria lopez",
        )
        sources_found = {
            h.source
            for h in result.items
        }
        assert (
            "identity"
            in sources_found
        )
        assert (
            "credential"
            in sources_found
        )
        assert (
            "document"
            in sources_found
        )
        top = result.items[0]
        assert (
            top.source == "identity"
        )
        assert top.score == 3
        assert result.total >= 3
    finally:
        net.close()


def test_unauthorized_and_unknown_source(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        with pytest.raises(
            SearchNotAuthorizedError
        ):
            net.search.search(
                app_id="malware",
                query="x",
            )
        net.profiles.register_app(
            app_id="ok",
            display_name="OK",
            scopes=("display_name",),
        )
        with pytest.raises(
            UnknownSourceError
        ):
            net.search.search(
                app_id="ok",
                query="x",
                sources=("ghost",),
            )
    finally:
        net.close()


def test_pagination_with_page(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="portal",
            display_name="Portal",
            scopes=("display_name",),
        )
        owner = (
            net.identity.register_identity(
                kind=(
                    IdentityKind.PERSON
                ),
                display_name="o",
                actor="portal",
            )
        )
        for i in range(5):
            net.exchange.seal_document(
                owner_zid=owner.zid,
                title=(
                    f"Lote especial"
                    f" {i}"
                ),
                content=(
                    f"c{i}".encode()
                ),
                actor_app="portal",
            )
        page1 = net.search.search(
            app_id="portal",
            query="lote especial",
            offset=0,
            limit=2,
        )
        assert page1.total == 5
        assert len(page1.items) == 2
        assert (
            page1.has_more is True
        )
        assert (
            page1.next_offset == 2
        )
        page3 = net.search.search(
            app_id="portal",
            query="lote especial",
            offset=4,
            limit=2,
        )
        assert (
            len(page3.items) == 1
        )
        assert (
            page3.has_more is False
        )
    finally:
        net.close()


def test_every_query_audited(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="portal",
            display_name="Portal",
            scopes=("display_name",),
        )
        net.search.search(
            app_id="portal",
            query="algo",
        )
        net.search.search(
            app_id="portal",
            query="otro",
        )
        assert (
            net.search
            .search_log_count()
            == 2
        )
        assert (
            net.audit.verify() >= 2
        )
        net.telemetry.ingest_outbox(
            net.outbox
        )
        events = (
            net.telemetry.query_events(
                event_type=(
                    "network.search"
                    ".performed"
                )
            )
        )
        assert len(events) == 2
    finally:
        net.close()

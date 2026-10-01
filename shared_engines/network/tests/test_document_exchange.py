"""Verification package proofs: seal, offline
buyer verification, tampering detection, signature
request flow, reject + unauthorized app."""
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
from shared_engines.network.portable_profile import (
    ProfileRegistry,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
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
            "network.document.sealed",
            "network.signature"
            ".requested",
            "network.document.signed",
            "network.document.rejected",
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

    def close(self) -> None:
        self.db.close()


def test_seal_and_buyer_verifies_offline(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="marketplace",
            display_name="Market",
            scopes=("display_name",),
        )
        seller = (
            net.identity.register_identity(
                kind=(
                    IdentityKind.PERSON
                ),
                display_name="seller",
                actor="marketplace",
            )
        )
        contract = (
            b"CONTRATO DE VENTA v1"
        )
        sealed = (
            net.exchange.seal_document(
                owner_zid=seller.zid,
                title="Contrato",
                content=contract,
                actor_app=(
                    "marketplace"
                ),
            )
        )
        verdict = (
            net.exchange.verify_document(
                document_id=(
                    sealed.document_id
                ),
                content=contract,
            )
        )
        assert (
            verdict.authentic is True
        )
        assert (
            DocumentExchange
            .offline_verify(
                document_id=(
                    sealed.document_id
                ),
                content=contract,
                signature=(
                    sealed
                    .network_signature
                ),
                public_pem=(
                    sealed.public_pem
                ),
            )
            is True
        )
    finally:
        net.close()


def test_tampered_document_detected(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="marketplace",
            display_name="Market",
            scopes=("display_name",),
        )
        seller = (
            net.identity.register_identity(
                kind=(
                    IdentityKind.PERSON
                ),
                display_name="s",
                actor="marketplace",
            )
        )
        sealed = (
            net.exchange.seal_document(
                owner_zid=seller.zid,
                title="T",
                content=b"original",
                actor_app=(
                    "marketplace"
                ),
            )
        )
        verdict = (
            net.exchange.verify_document(
                document_id=(
                    sealed.document_id
                ),
                content=b"altered!",
            )
        )
        assert (
            verdict.authentic is False
        )
        assert (
            DocumentExchange
            .offline_verify(
                document_id=(
                    sealed.document_id
                ),
                content=b"altered!",
                signature=(
                    sealed
                    .network_signature
                ),
                public_pem=(
                    sealed.public_pem
                ),
            )
            is False
        )
    finally:
        net.close()


def test_signature_request_flow(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="marketplace",
            display_name="Market",
            scopes=("display_name",),
        )
        seller = (
            net.identity.register_identity(
                kind=(
                    IdentityKind.PERSON
                ),
                display_name="s",
                actor="marketplace",
            )
        )
        buyer = (
            net.identity.register_identity(
                kind=(
                    IdentityKind.PERSON
                ),
                display_name="b",
                actor="marketplace",
            )
        )
        sealed = (
            net.exchange.seal_document(
                owner_zid=seller.zid,
                title="Acuerdo",
                content=b"acuerdo v1",
                actor_app=(
                    "marketplace"
                ),
            )
        )
        req = (
            net.exchange
            .request_signature(
                document_id=(
                    sealed.document_id
                ),
                signer_zid=buyer.zid,
                requester_zid=(
                    seller.zid
                ),
            )
        )
        assert req.status == "PENDING"
        assert len(
            net.exchange.pending_for(
                signer_zid=buyer.zid
            )
        ) == 1
        signed = (
            net.exchange.sign_request(
                request_id=req.request_id,
                signer_zid=buyer.zid,
            )
        )
        assert signed.status == "SIGNED"
        assert (
            signed.signature is not None
        )
        assert len(
            net.exchange.pending_for(
                signer_zid=buyer.zid
            )
        ) == 0
        assert (
            DocumentExchange
            .verify_signature_receipt(
                request_id=req.request_id,
                document_id=(
                    sealed.document_id
                ),
                sha256=sealed.sha256,
                signer_zid=buyer.zid,
                signature=(
                    signed.signature
                ),
                public_pem=(
                    sealed.public_pem
                ),
            )
            is True
        )
        with pytest.raises(ValueError):
            net.exchange.sign_request(
                request_id=(
                    req.request_id
                ),
                signer_zid=buyer.zid,
            )
    finally:
        net.close()


def test_reject_and_unauthorized_app(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="marketplace",
            display_name="Market",
            scopes=("display_name",),
        )
        a = (
            net.identity.register_identity(
                kind=(
                    IdentityKind.PERSON
                ),
                display_name="a",
                actor="marketplace",
            )
        )
        b = (
            net.identity.register_identity(
                kind=(
                    IdentityKind.PERSON
                ),
                display_name="b",
                actor="marketplace",
            )
        )
        sealed = (
            net.exchange.seal_document(
                owner_zid=a.zid,
                title="T",
                content=b"x",
                actor_app=(
                    "marketplace"
                ),
            )
        )
        req = (
            net.exchange
            .request_signature(
                document_id=(
                    sealed.document_id
                ),
                signer_zid=b.zid,
                requester_zid=a.zid,
            )
        )
        rejected = (
            net.exchange
            .reject_request(
                request_id=req.request_id,
                signer_zid=b.zid,
            )
        )
        assert (
            rejected.status
            == "REJECTED"
        )
        with pytest.raises(
            ValueError
        ):
            net.exchange.sign_request(
                request_id=(
                    req.request_id
                ),
                signer_zid=b.zid,
            )
        with pytest.raises(
            PermissionError
        ):
            net.exchange.seal_document(
                owner_zid=a.zid,
                title="T",
                content=b"y",
                actor_app="malware",
            )
    finally:
        net.close()


def test_register_list_filter_and_versions(
    tmp_path: Path,
) -> None:
    """AX-DOCS v2: registrar,
    filtrar, versionar; verificacion
    intacta; Red solo indice."""
    import hashlib as _hl
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="marketplace",
            display_name="Market",
            scopes=(
                "display_name",),
        )
        owner = (
            net.identity
            .register_identity(
                kind=(
                    IdentityKind
                    .PERSON),
                display_name=(
                    "docowner"),
                actor=(
                    "marketplace"),
            )
        )
        contenido = (
            b"FACTURA-PDF-001")
        rec = (
            net.exchange
            .register_document(
                owner_zid=(
                    owner.zid),
                title="Factura 001",
                content=contenido,
                doc_kind="pdf",
                purpose=(
                    "factura-"
                    "hacienda"),
                storage_ref=(
                    "nexo://"
                    "facturas/001"),
                actor_app=(
                    "marketplace"),
            )
        )
        assert rec[
            "document_id"
        ].startswith("DOC-")
        assert rec["sha256"] == (
            _hl.sha256(
                contenido
            ).hexdigest())
        docs = (
            net.exchange
            .list_documents(
                owner_zid=(
                    owner.zid))
        )
        assert len(docs) == 1
        assert docs[0][
            "doc_kind"] == "pdf"
        assert docs[0][
            "purpose"
        ] == "factura-hacienda"
        assert docs[0][
            "storage_ref"
        ] == "nexo://facturas/001"
        assert (
            net.exchange
            .list_documents(
                owner_zid=(
                    owner.zid),
                purpose="otro",
            ) == ()
        )
        assert (
            net.exchange
            .list_documents(
                owner_zid=(
                    owner.zid),
                kind="word",
            ) == ()
        )
        v = (
            net.exchange
            .verify_document(
                document_id=(
                    rec[
                        "document_id"]),
                content=contenido,
            )
        )
        assert v.authentic is True
        v2 = (
            net.exchange
            .new_version_index(
                document_id=(
                    rec[
                        "document_id"]),
                content=(
                    b"FACTURA-"
                    b"PDF-001-v2"),
                doc_kind="pdf",
                purpose=(
                    "factura-"
                    "hacienda"),
                storage_ref=(
                    "nexo://"
                    "facturas/001"
                    "/v2"),
                actor_app=(
                    "marketplace"),
            )
        )
        assert v2["prev_version"] == (
            rec["document_id"])
        docs = (
            net.exchange
            .list_documents(
                owner_zid=(
                    owner.zid))
        )
        assert len(docs) == 2
        v2check = (
            net.exchange
            .verify_document(
                document_id=v2[
                    "document_id"],
                content=(
                    b"FACTURA-"
                    b"PDF-001-v2"),
            )
        )
        assert (
            v2check.authentic is True)
        v1check = (
            net.exchange
            .verify_document(
                document_id=(
                    rec[
                        "document_id"]),
                content=contenido,
            )
        )
        assert (
            v1check.authentic is True)
    finally:
        net.close()


def test_register_unauthorized_app(
    tmp_path: Path,
) -> None:
    """AX-DOCS v2: app no registrada
    -> rechazada; indice vacio."""
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="marketplace",
            display_name="Market",
            scopes=(
                "display_name",),
        )
        owner = (
            net.identity
            .register_identity(
                kind=(
                    IdentityKind
                    .PERSON),
                display_name="o2",
                actor=(
                    "marketplace"),
            )
        )
        with pytest.raises(
            PermissionError
        ):
            net.exchange.register_document(
                owner_zid=(
                    owner.zid),
                title="X",
                content=b"y",
                doc_kind="json",
                purpose="p",
                storage_ref="ref",
                actor_app="malware",
            )
        assert (
            net.exchange
            .list_documents(
                owner_zid=(
                    owner.zid))
            == ()
        )
    finally:
        net.close()

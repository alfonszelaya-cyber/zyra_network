"""Capabilities HTTP proofs: the family-consumer
journey over real HTTP, following the existing
ZyraServer test pattern (real server on a thread,
urllib, explicit shutdown)."""
from __future__ import annotations

import base64
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import (
    IdentityKind,
)
from shared_engines.identity.engine import IdentityEngine
from shared_engines.runtime.capabilities import (
    ZyraCapabilities,
)
from shared_engines.runtime.capabilities_api import (
    CapabilitiesApiHandler,
    CapabilitiesServer,
)
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.signatures import (
    Ed25519Signer,
)


class _Http:
    """Real server harness, existing-pattern."""

    def __init__(self, tmp_path: Path) -> None:
        self.db = SQLiteAdapter(
            tmp_path / "api.db"
        )
        self.clock = FrozenClock()
        audit = AuditTrail(self.db, self.clock)
        outbox = Outbox(self.db, self.clock)
        outbox.ensure_schema()
        catalog = EventCatalog()
        for et in (
            "identity.registered",
            "identity.status_changed",
        ):
            catalog.register(et)
        self.identity = IdentityEngine(
            db=self.db,
            clock=self.clock,
            audit=audit,
            outbox=outbox,
            catalog=catalog,
        )
        signer, _ = Ed25519Signer.generate()
        self.caps = ZyraCapabilities(
            self.db,
            self.clock,
            identity=self.identity,
            signer=signer,
        )
        CapabilitiesApiHandler.caps = self.caps
        self.server = CapabilitiesServer(
            ("127.0.0.1", 0)
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()
        self.base = (
            "http://127.0.0.1:"
            f"{self.server.bound_port}"
        )

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.db.close()


def _get(url: str) -> dict[str, object]:
    with urlopen(url, timeout=10) as response:
        body = json.loads(
            response.read().decode("utf-8")
        )
    assert isinstance(body, dict)
    return body


def _post(
    url: str, doc: dict[str, object]
) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(doc).encode("utf-8"),
        headers={
            "Content-Type":
            "application/json"
        },
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        body = json.loads(
            response.read().decode("utf-8")
        )
    assert isinstance(body, dict)
    return body


def test_health_profile_trust_journey(
    tmp_path: Path,
) -> None:
    http = _Http(tmp_path)
    try:
        health = _get(f"{http.base}/health")
        assert health["ok"] is True
        _post(
            f"{http.base}/apps/register",
            {
                "app_id": "familia",
                "display_name": "Familia",
                "scopes": [
                    "display_name",
                    "contact",
                ],
            },
        )
        user = http.identity.register_identity(
            kind=IdentityKind.PERSON,
            display_name="maria",
            actor="familia",
        )
        _post(
            f"{http.base}/profile/field",
            {
                "zid": user.zid,
                "field": "display_name",
                "value": "Maria Lopez",
            },
        )
        _post(
            f"{http.base}/profile/field",
            {
                "zid": user.zid,
                "field": "contact",
                "value": "maria@zyra.sv",
            },
        )
        view = _get(
            f"{http.base}/profile/"
            f"{user.zid}?app=familia"
        )
        data = view["data"]
        assert isinstance(data, dict)
        fields = data["fields"]
        assert isinstance(fields, dict)
        assert (
            fields["display_name"]
            == "Maria Lopez"
        )
        complete = _post(
            f"{http.base}/trust/complete",
            {
                "zid": user.zid,
                "actor": "verifier",
            },
        )
        cdata = complete["data"]
        assert isinstance(cdata, dict)
        assert cdata["status"] == "ACTIVE"
        trust = _get(
            f"{http.base}/trust/{user.zid}"
        )
        tdata = trust["data"]
        assert isinstance(tdata, dict)
        assert tdata["trusted"] is True
    finally:
        http.close()


def test_history_documents_journey(
    tmp_path: Path,
) -> None:
    http = _Http(tmp_path)
    try:
        caps_profs = http.caps.profiles
        caps_profs.register_app(
            app_id="familia",
            display_name="Familia",
            scopes=("display_name",),
        )
        user = http.identity.register_identity(
            kind=IdentityKind.PERSON,
            display_name="bebe",
            actor="familia",
        )
        appended = _post(
            f"{http.base}/history/append",
            {
                "zid": user.zid,
                "entry_type": (
                    "birth_registration"
                ),
                "actor_app": "familia",
                "payload": {
                    "hospital":
                    "San Salvador"
                },
            },
        )
        adata = appended["data"]
        assert isinstance(adata, dict)
        assert adata["seq"] == 1
        timeline = _get(
            f"{http.base}/history/"
            f"{user.zid}"
        )
        hdata = timeline["data"]
        assert isinstance(hdata, list)
        assert len(hdata) == 1
        sealed = _post(
            f"{http.base}/documents/seal",
            {
                "owner_zid": user.zid,
                "title": "Acta",
                "content_b64": base64.b64encode(
                    b"acta original"
                ).decode("ascii"),
                "actor_app": "familia",
            },
        )
        sdata = sealed["data"]
        assert isinstance(sdata, dict)
        document_id = sdata["document_id"]
        good = _post(
            f"{http.base}/documents/verify",
            {
                "document_id": document_id,
                "content_b64": base64.b64encode(
                    b"acta original"
                ).decode("ascii"),
            },
        )
        gdata = good["data"]
        assert isinstance(gdata, dict)
        assert gdata["authentic"] is True
        bad = _post(
            f"{http.base}/documents/verify",
            {
                "document_id": document_id,
                "content_b64": base64.b64encode(
                    b"acta falsificada"
                ).decode("ascii"),
            },
        )
        bdata = bad["data"]
        assert isinstance(bdata, dict)
        assert bdata["authentic"] is False
    finally:
        http.close()


def test_search_reputation_and_guard(
    tmp_path: Path,
) -> None:
    http = _Http(tmp_path)
    try:
        http.caps.profiles.register_app(
            app_id="familia",
            display_name="Familia",
            scopes=("display_name",),
        )
        worker = (
            http.identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name="carlos ruiz",
                actor="familia",
            )
        )
        employer = (
            http.identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name="empleador",
                actor="familia",
            )
        )
        recorded = _post(
            f"{http.base}/reputation/record",
            {
                "subject_zid": worker.zid,
                "actor_zid": employer.zid,
                "kind": "positive",
                "evidence_b64": base64.b64encode(
                    b"contrato firmado"
                ).decode("ascii"),
            },
        )
        rdata = recorded["data"]
        assert isinstance(rdata, dict)
        assert rdata["seq"] == 1
        summary = _get(
            f"{http.base}/reputation/"
            f"{worker.zid}"
        )
        sdata = summary["data"]
        assert isinstance(sdata, dict)
        assert sdata["score"] == 10
        result = _post(
            f"{http.base}/search",
            {
                "app_id": "familia",
                "query": "carlos ruiz",
            },
        )
        data = result["data"]
        assert isinstance(data, dict)
        assert data["total"] >= 1
        with pytest.raises(HTTPError) as exc:
            _post(
                f"{http.base}/search",
                {
                    "app_id": "malware",
                    "query": "x",
                },
            )
        assert exc.value.code == 400
    finally:
        http.close()

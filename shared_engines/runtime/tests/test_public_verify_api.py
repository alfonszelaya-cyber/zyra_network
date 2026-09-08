from __future__ import annotations

import base64
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import IdentityKind
from shared_engines.identity.engine import IdentityEngine
from shared_engines.runtime.api import ZyraApiHandler
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.runtime.server import ZyraServer
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.attestations import AttestationIssuer
from shared_engines.verification.signatures import Ed25519Signer


class _Cluster:
    def __init__(self, tmp_path: Path) -> None:
        self.db = SQLiteAdapter(Path(tmp_path) / "runtime.db")
        self.kernel = ZyraKernel(
            db=self.db,
            clock=FrozenClock(),
            signer=Ed25519Signer.generate()[0],
            config=RuntimeConfig(host="127.0.0.1", port=0),
        )
        self.kernel.bootstrap_root()
        ZyraApiHandler.kernel = self.kernel
        self.server = ZyraServer(("127.0.0.1", 0))
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.bound_port}"

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.db.close()

    def call(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        headers: dict[str, str] = {
            "Content-Type": "application/json"
        }
        data = (
            json.dumps(body).encode("utf-8")
            if body is not None
            else None
        )
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(
                request, timeout=10
            ) as resp:
                payload: dict[str, Any] = json.loads(
                    resp.read().decode("utf-8")
                )
                return int(resp.status), payload
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8") or "{}"
            error_payload: dict[str, Any] = json.loads(raw)
            return int(exc.code), error_payload


@pytest.fixture
def cluster(tmp_path: Path) -> Iterator[_Cluster]:
    running = _Cluster(tmp_path)
    yield running
    running.stop()


def _mint_attestation(tmp_path: Path) -> str:
    db = SQLiteAdapter(tmp_path / "mint.db")
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    catalog = EventCatalog()
    catalog.register("verification.attestation.issued")
    catalog.register("identity.registered")
    catalog.register("identity.status_changed")
    identity = IdentityEngine(
        db=db,
        clock=clock,
        audit=audit,
        outbox=outbox,
        catalog=catalog,
    )
    subject = identity.register_identity(
        kind=IdentityKind.PERSON,
        display_name="Public",
        actor="registrar",
    )
    signer, _ = Ed25519Signer.generate()
    issuer = AttestationIssuer(
        db=db,
        clock=clock,
        signer=signer,
        audit=audit,
        outbox=outbox,
        catalog=catalog,
    )
    attestation = issuer.issue(
        subject_zid=subject.zid, claim="identity_active"
    )
    db.close()
    return json.dumps(
        {
            "format": "zyra.attestation.v1",
            "attestation_id": attestation.attestation_id,
            "subject_zid": attestation.subject_zid,
            "claim": attestation.claim,
            "subject_sha256": attestation.subject_sha256,
            "issued_at": attestation.issued_at,
            "signature_b64": base64.b64encode(
                attestation.signature
            ).decode("ascii"),
            "signer_public_pem": attestation.signer_public_pem.decode(
                "utf-8"
            ),
        }
    )


def test_public_verify_accepts_authentic(
    cluster: _Cluster, tmp_path: Path,
) -> None:
    blob = _mint_attestation(tmp_path)
    status, payload = cluster.call(
        "POST", "/verify", {"attestation": blob}
    )
    assert status == 200
    assert payload["ok"] is True
    assert payload["data"]["valid"] is True
    assert "AUTHENTIC" in payload["data"]["reason"]


def test_public_verify_rejects_tampered(
    cluster: _Cluster, tmp_path: Path,
) -> None:
    blob = _mint_attestation(tmp_path)
    doc = json.loads(blob)
    doc["claim"] = "forged"
    status, payload = cluster.call(
        "POST", "/verify", {"attestation": json.dumps(doc)}
    )
    assert status == 200
    assert payload["data"]["valid"] is False
    assert "INVALID" in payload["data"]["reason"]


def test_public_verify_is_open_without_auth(
    cluster: _Cluster, tmp_path: Path,
) -> None:
    blob = _mint_attestation(tmp_path)
    status, payload = cluster.call(
        "POST", "/verify", {"attestation": blob}
    )
    assert status == 200
    assert payload["ok"] is True

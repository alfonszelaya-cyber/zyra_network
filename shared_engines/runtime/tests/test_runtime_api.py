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

from shared_engines.common.clocks import FrozenClock
from shared_engines.runtime.api import ZyraApiHandler
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.runtime.server import ZyraServer
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.signatures import Ed25519Signer


class _Cluster:
    """Boots a real HTTP server over a live kernel."""

    def __init__(
        self, tmp_path: Path, token: str | None = None
    ) -> None:
        self.db = SQLiteAdapter(Path(tmp_path) / "runtime.db")
        self.kernel = ZyraKernel(
            db=self.db,
            clock=FrozenClock(),
            signer=Ed25519Signer.generate()[0],
            config=RuntimeConfig(
                host="127.0.0.1", port=0, api_token=token
            ),
        )
        self.kernel.bootstrap_root()
        ZyraApiHandler.kernel = self.kernel
        self.server = ZyraServer(("127.0.0.1", 0))
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        self.base = (
            f"http://127.0.0.1:{self.server.bound_port}"
        )

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
        *,
        token: str | None = None,
        omit_auth: bool = False,
    ) -> tuple[int, dict[str, Any]]:
        headers: dict[str, str] = {
            "Content-Type": "application/json"
        }
        if not omit_auth:
            use = (
                token
                if token is not None
                else self.kernel.config.api_token
            )
            if use is not None:
                headers["Authorization"] = f"Bearer {use}"
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


@pytest.fixture
def secured_cluster(tmp_path: Path) -> Iterator[_Cluster]:
    running = _Cluster(tmp_path, token="super-secret-token-123")
    yield running
    running.stop()


def _register_via_api(
    cluster: _Cluster, name: str
) -> dict[str, Any]:
    status, payload = cluster.call(
        "POST",
        "/identity/register",
        {
            "kind": "organization",
            "display_name": name,
            "actor": "api-clerk",
        },
    )
    assert status == 201
    assert payload["ok"] is True
    data: dict[str, Any] = payload["data"]
    return data


def _activate_via_api(
    cluster: _Cluster, zid: str
) -> dict[str, Any]:
    status, payload = cluster.call(
        "POST",
        "/identity/transition",
        {
            "zid": zid,
            "to_status": "ACTIVE",
            "actor": "api-admin",
            "reason": "onboarded",
        },
    )
    assert status == 200
    data: dict[str, Any] = payload["data"]
    return data


def test_health_is_open_and_reports_components(
    cluster: _Cluster,
) -> None:
    status, payload = cluster.call(
        "GET", "/health", omit_auth=True
    )
    assert status == 200
    assert payload["ok"] is True
    assert payload["data"]["overall"]["status"] == "healthy"
    names = {
        c["component"] for c in payload["data"]["components"]
    }
    assert {"storage", "identity", "verification"} <= names


def test_identity_register_get_transition_flow(
    cluster: _Cluster,
) -> None:
    created = _register_via_api(cluster, "Alice")
    zid = created["zid"]
    assert zid.startswith("ZID-")
    assert created["status"] == "REGISTERED"
    status, payload = cluster.call("GET", f"/identity/{zid}")
    assert status == 200
    assert payload["data"]["display_name"] == "Alice"
    moved = _activate_via_api(cluster, zid)
    assert moved["status"] == "ACTIVE"
    bad_status, bad = cluster.call(
        "POST",
        "/identity/transition",
        {
            "zid": zid,
            "to_status": "VERIFIED",
            "actor": "api-admin",
            "reason": "skips states",
        },
    )
    assert bad_status == 409
    assert bad["error"]["type"] == "conflict"


def test_unknown_identity_returns_404(
    cluster: _Cluster,
) -> None:
    status, payload = cluster.call("GET", "/identity/ZID-ghost")
    assert status == 404
    assert payload["error"]["type"] == "not_found"


def test_media_register_verify_tamper_via_http(
    cluster: _Cluster,
) -> None:
    owner = _activate_via_api(
        cluster, _register_via_api(cluster, "Owner")["zid"]
    )
    content = b"photo-bytes-original"
    encoded = base64.b64encode(content).decode("ascii")
    status, payload = cluster.call(
        "POST",
        "/verification/media",
        {
            "owner_zid": owner["zid"],
            "kind": "photo",
            "title": "photo.jpg",
            "content_b64": encoded,
            "content_type": "image/jpeg",
            "actor": "clerk",
        },
    )
    assert status == 201
    media_id = payload["data"]["media_id"]
    assert payload["data"]["content_sha256"]
    verify_status, _ = cluster.call(
        "POST",
        "/verification/media/verify",
        {"media_id": media_id, "content_b64": encoded},
    )
    assert verify_status == 200
    tamper_status, tamper = cluster.call(
        "POST",
        "/verification/media/verify",
        {
            "media_id": media_id,
            "content_b64": base64.b64encode(
                b"tampered"
            ).decode("ascii"),
        },
    )
    assert tamper_status == 409
    assert tamper["error"]["type"] == "conflict"
    history_status, history = cluster.call(
        "GET", f"/verification/media/{media_id}/history"
    )
    assert history_status == 200
    actions = [e["action"] for e in history["data"]]
    assert actions == ["registered", "verified"]


def test_media_requires_known_owner(
    cluster: _Cluster,
) -> None:
    status, _ = cluster.call(
        "POST",
        "/verification/media",
        {
            "owner_zid": "ZID-ghost",
            "kind": "photo",
            "title": "x.jpg",
            "content_b64": base64.b64encode(b"c").decode("ascii"),
            "content_type": "image/jpeg",
            "actor": "clerk",
        },
    )
    assert status == 404


def test_credential_full_flow_via_http(
    cluster: _Cluster,
) -> None:
    root = cluster.kernel.root_zid
    assert root is not None
    client = _activate_via_api(
        cluster, _register_via_api(cluster, "Bank Client")["zid"]
    )
    status, payload = cluster.call(
        "POST",
        "/verification/credentials",
        {
            "subject_zid": client["zid"],
            "issuer_zid": root,
            "credential_type": "kyc_verified",
            "title": "KYC completed",
            "detail": "verified in person",
        },
    )
    assert status == 201
    credential_id = payload["data"]["credential_id"]
    get_status, got = cluster.call(
        "GET", f"/verification/credentials/{credential_id}"
    )
    assert get_status == 200
    assert got["data"]["credential_type"] == "kyc_verified"
    list_status, listed = cluster.call(
        "GET",
        f"/verification/subjects/{client['zid']}/credentials",
    )
    assert list_status == 200
    assert len(listed["data"]) == 1
    revoke_status, revoked = cluster.call(
        "POST",
        "/verification/credentials/revoke",
        {
            "credential_id": credential_id,
            "revoked_by": root,
            "reason": "manual review",
        },
    )
    assert revoke_status == 200
    assert revoked["data"]["revoked"] is True


def test_credential_issuer_must_be_active(
    cluster: _Cluster,
) -> None:
    subject = _activate_via_api(
        cluster, _register_via_api(cluster, "S")["zid"]
    )
    inst_status, inst = cluster.call(
        "POST",
        "/identity/register",
        {
            "kind": "institution",
            "display_name": "Inactive Inst",
            "actor": "api-clerk",
        },
    )
    assert inst_status == 201
    status, payload = cluster.call(
        "POST",
        "/verification/credentials",
        {
            "subject_zid": subject["zid"],
            "issuer_zid": inst["data"]["zid"],
            "credential_type": "reference",
            "title": "ref",
            "detail": "issuer is only REGISTERED",
        },
    )
    assert status == 403
    assert payload["error"]["type"] == "forbidden"


def test_attestation_issue_and_verify_via_http(
    cluster: _Cluster,
) -> None:
    subject = _activate_via_api(
        cluster, _register_via_api(cluster, "Attested")["zid"]
    )
    status, payload = cluster.call(
        "POST",
        "/verification/attestations",
        {
            "subject_zid": subject["zid"],
            "claim": "identity_active",
        },
    )
    assert status == 201
    attestation_id = payload["data"]["attestation_id"]
    assert payload["data"]["signature_b64"]
    verify_status, verified = cluster.call(
        "POST",
        "/verification/attestations/verify",
        {"attestation_id": attestation_id},
    )
    assert verify_status == 200
    assert verified["data"]["valid"] is True


def test_auth_required_and_accepted(
    secured_cluster: _Cluster,
) -> None:
    secured = secured_cluster
    no_token_status, no_token = secured.call(
        "POST",
        "/identity/register",
        {"kind": "organization", "display_name": "X", "actor": "a"},
        omit_auth=True,
    )
    assert no_token_status == 401
    assert no_token["error"]["type"] == "unauthorized"
    wrong_status, _ = secured.call(
        "POST",
        "/identity/register",
        {"kind": "organization", "display_name": "X", "actor": "a"},
        token="wrong-token-wrong-token",
    )
    assert wrong_status == 401
    good_status, _ = secured.call(
        "POST",
        "/identity/register",
        {"kind": "organization", "display_name": "X", "actor": "a"},
    )
    assert good_status == 201
    health_status, _ = secured.call(
        "GET", "/health", omit_auth=True
    )
    assert health_status == 200


def test_unknown_route_and_bad_json(
    cluster: _Cluster,
) -> None:
    status, _ = cluster.call("GET", "/definitely/not/here")
    assert status == 404
    bad_status, _ = cluster.call(
        "POST",
        "/identity/register",
        {"kind": "organization", "display_name": "", "actor": "a"},
    )
    assert bad_status == 400


def test_root_authority_is_active_and_persistent(
    cluster: _Cluster,
) -> None:
    root = cluster.kernel.root_zid
    assert root is not None
    status, payload = cluster.call("GET", f"/identity/{root}")
    assert status == 200
    assert payload["data"]["status"] == "ACTIVE"
    assert payload["data"]["kind"] == "institution"


def test_kernel_health_after_crash_of_storage(
    tmp_path: Path,
) -> None:
    cluster = _Cluster(tmp_path)
    try:
        assert (
            cluster.kernel.health().status.value == "healthy"
        )
    finally:
        cluster.stop()
    assert (
        cluster.kernel.health().status.value == "unhealthy"
    )


def test_audit_chain_covers_api_traffic(
    cluster: _Cluster,
) -> None:
    _register_via_api(cluster, "Audited 1")
    _register_via_api(cluster, "Audited 2")
    subject = _activate_via_api(
        cluster, _register_via_api(cluster, "Audited 3")["zid"]
    )
    root = cluster.kernel.root_zid
    assert root is not None
    cred_status, _ = cluster.call(
        "POST",
        "/verification/credentials",
        {
            "subject_zid": subject["zid"],
            "issuer_zid": root,
            "credential_type": "employment",
            "title": "Hired",
            "detail": "via API",
        },
    )
    assert cred_status == 201
    count = cluster.kernel.audit.verify()
    assert count >= 5


def test_person_register_is_bypass_blocked(
    cluster: _Cluster,
) -> None:
    """HARDENING: creating a PERSON via the legacy
    door is refused - persons must go through
    /identity/enroll (mandatory biometrics)."""
    status, payload = cluster.call(
        "POST",
        "/identity/register",
        {
            "kind": "person",
            "display_name": "Bypass Try",
            "actor": "attacker",
        },
    )
    assert status == 403
    assert (
        payload["error"]["type"]
        == "person_bypass_forbidden"
    )


def test_verify_existence_public(
    tmp_path,
) -> None:
    """AX-NIVEL1: consulta publica de
    existencia - mata documentos
    falsos. Solo existe/status; cero
    datos personales en la respuesta."""
    import json as _json
    import threading
    import time as _time
    import urllib.request
    from shared_engines.storage.database import (
        SQLiteAdapter)
    from shared_engines.common.clocks import (
        FrozenClock)
    from shared_engines.runtime.config import (
        RuntimeConfig)
    from shared_engines.runtime.kernel import (
        ZyraKernel)
    from shared_engines.runtime.capabilities import (
        ZyraCapabilities)
    from shared_engines.runtime.combined_api import (
        serve_combined)
    from shared_engines.verification.signatures import (
        Ed25519Signer)
    from shared_engines.identity.contracts import (
        IdentityKind)
    net_db = SQLiteAdapter(":memory:")
    signer, _ = Ed25519Signer.generate()
    kernel = ZyraKernel(
        db=net_db,
        clock=FrozenClock(),
        signer=signer,
        config=RuntimeConfig(
            host="127.0.0.1",
            port=0,
            api_token=None))
    kernel.bootstrap_root()
    caps = ZyraCapabilities(
        net_db, FrozenClock(),
        identity=kernel.identity,
        signer=signer)
    srv = serve_combined(
        kernel, caps,
        host="127.0.0.1", port=0)
    threading.Thread(
        target=(srv.serve_forever),
        daemon=True).start()
    _time.sleep(0.3)
    base = ("http://127.0.0.1:"
            + str(
                srv.server_address[
                    1]))
    try:
        real = (kernel.identity
            .register_identity(
                kind=(
                    IdentityKind
                    .PERSON),
                display_name=(
                    "Pedro Real"),
                actor="test"))
        def get(zid):
            with urllib.request.urlopen(
                base
                + "/verify-existence/"
                + zid,
                timeout=15,
            ) as r:
                return (r.status,
                    _json.loads(
                        r.read().decode()))

        st, r1 = get(real.zid)
        assert st == 200, str(r1)
        d1 = r1["data"]
        assert d1["exists"] is True
        assert d1["status"] in (
            "REGISTERED", "ACTIVE")
        assert "display_name" not in (
            str(d1))
        assert "birth" not in (
            str(d1).lower())
        assert "national" not in (
            str(d1).lower())

        st, r2 = get(
            "ZID-falso-estafador-000")
        assert st == 200
        d2 = r2["data"]
        assert d2["exists"] is False
        print("OK AX-NIVEL1: existencia"
              " publica funciona (real:"
              " existe; falso: no existe)"
              " y NO filtra datos"
              " personales")
    finally:
        srv.shutdown()
        srv.server_close()


def test_death_lifecycle_deceased(tmp_path) -> None:
    """AX-DEATH: ACTIVE -> DECEASED -> verify-existence lo muestra -> terminal."""
    import json as _json
    import threading
    import time as _time
    import urllib.request
    from shared_engines.storage.database import SQLiteAdapter
    from shared_engines.common.clocks import FrozenClock
    from shared_engines.runtime.config import RuntimeConfig
    from shared_engines.runtime.kernel import ZyraKernel
    from shared_engines.runtime.capabilities import ZyraCapabilities
    from shared_engines.runtime.combined_api import serve_combined
    from shared_engines.verification.signatures import Ed25519Signer
    from shared_engines.security.biometrics import BiometricsEngine, BiometricsPolicy, DeterministicTestProvider, TemplateCipher
    from shared_engines.identity.contracts import IdentityStatus
    net_db = SQLiteAdapter(":memory:")
    signer, _ = Ed25519Signer.generate()
    kernel = ZyraKernel(db=net_db, clock=FrozenClock(), signer=signer, config=RuntimeConfig(host="127.0.0.1", port=0, api_token=None))
    kernel.bootstrap_root()
    kernel._biometrics = BiometricsEngine(db=net_db, clock=FrozenClock(), audit=kernel.audit, provider=DeterministicTestProvider(), cipher=TemplateCipher(master_key_hex="ab" * 32), policy=BiometricsPolicy(require_liveness=False, doc_reject=0.01, doc_review=0.02, doc_auto=0.03, dup_reject=0.98))
    caps = ZyraCapabilities(net_db, FrozenClock(), identity=kernel.identity, signer=signer)
    srv = serve_combined(kernel, caps, host="127.0.0.1", port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    _time.sleep(0.3)
    base = "http://127.0.0.1:" + str(srv.server_address[1])

    def post(ruta, doc):
        data = _json.dumps(doc).encode()
        req = urllib.request.Request(base + ruta, data=data, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, _json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, _json.loads(e.read().decode())

    try:
        st, r1 = post("/identity/enroll", {"kind": "person", "display_name": "Pedro Ciclo", "actor": "test", "doc_image_b64": "cGVkcm8tZG9j", "selfie_image_b64": "cGVkcm8tc2VsZmll"})
        assert st in (200, 201), str(st) + " " + str(r1)
        zid = ((r1.get("data") or {}).get("identity") or {}).get("zid")
        assert zid, str(r1)[:300]
        kernel.identity.transition_identity(zid, IdentityStatus.ACTIVE, actor="test", reason="onboarding")
        st, r2 = post("/identity/transition", {"zid": zid, "to_status": "DECEASED", "actor": "registrador", "reason": "acta de defuncion 2025-001"})
        assert st in (200, 201), str(st) + " " + str(r2)[:300]
        ident = kernel.identity.get_identity(zid)
        assert ident.status == IdentityStatus.DECEASED, str(ident)
        with urllib.request.urlopen(base + "/verify-existence/" + zid, timeout=15) as r:
            d = _json.loads(r.read().decode())
        assert d["data"]["exists"] is True
        assert d["data"]["status"] == "DECEASED"
        assert d["data"]["active"] is False
        bloq = False
        try:
            kernel.identity.transition_identity(zid, IdentityStatus.ACTIVE, actor="fraud", reason="intento")
        except Exception:
            bloq = True
        assert bloq, "DECEASED debe ser terminal"
        evs = net_db.query_all("SELECT event_type FROM events_outbox WHERE aggregate_id = ? ORDER BY created_at", (zid,))
        tipos = [str(r["event_type"]) for r in evs]
        assert "identity.status_changed" in tipos, str(tipos)
        print("OK AX-DEATH: ACTIVE -> DECEASED, terminal, verify-existence lo refleja, evento al outbox para el cartero")
    finally:
        srv.shutdown()
        srv.server_close()

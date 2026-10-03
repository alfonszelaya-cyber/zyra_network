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


def test_history_via_serve_combined(
    tmp_path: Path,
) -> None:
    """Regresion RED-1: el camino
    real de las apps (serve_combined)
    debe servir GET /history/{zid}
    sin 500 (override _route_get de
    CombinedHandler sin query)."""
    import base64
    import json as _json
    import threading
    import time
    import urllib.error
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
    from shared_engines.security.biometrics import (
        BiometricsEngine, BiometricsPolicy,
        DeterministicTestProvider,
        TemplateCipher)
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
    kernel._biometrics = BiometricsEngine(
        db=net_db,
        clock=FrozenClock(),
        audit=kernel.audit,
        provider=(
            DeterministicTestProvider()),
        cipher=TemplateCipher(
            master_key_hex="ab" * 32),
        policy=BiometricsPolicy(
            require_liveness=False,
            doc_reject=0.01,
            doc_review=0.02,
            doc_auto=0.03,
            dup_reject=0.98))
    caps = ZyraCapabilities(
        net_db, FrozenClock(),
        identity=kernel.identity,
        signer=signer)
    srv = serve_combined(
        kernel, caps,
        host="127.0.0.1", port=0)
    threading.Thread(
        target=srv.serve_forever,
        daemon=True).start()
    time.sleep(0.3)
    base = ("http://127.0.0.1:"
            + str(
                srv.server_address[1]))
    try:
        req = urllib.request.Request(
            base
            + "/identity/enroll",
            data=_json.dumps({
                "kind": "person",
                "display_name": (
                    "RegUser"),
                "actor": "reg",
                "doc_image_b64": (
                    base64.b64encode(
                        b"reg-history"
                    ).decode("ascii")),
                "selfie_image_b64": (
                    base64.b64encode(
                        b"reg-history"
                    ).decode("ascii")),
            }).encode(),
            method="POST",
            headers={
                "Content-Type":
                "application/json"})
        with urllib.request.urlopen(
            req,
            timeout=15) as r:
            body = _json.loads(
                r.read().decode())
        zid = ((body.get("data")
                or {}).get("identity")
               or {}).get("zid")
        assert zid

        def _get(ruta):
            try:
                with urllib.request.urlopen(
                    base + ruta,
                    timeout=15
                ) as r2:
                    return (r2.status,
                        _json.loads(
                            r2.read().decode()))
            except (
                urllib.error.HTTPError
            ) as e2:
                return (e2.code,
                    _json.loads(
                        e2.read().decode()))

        st, resp = _get(
            "/history/" + zid)
        assert st == 200, (
            "history " + str(st)
            + " " + str(resp))
        assert resp["data"] == [], (
            str(resp))
        st, resp = _get(
            "/trust/" + zid)
        assert st == 200, (
            "trust " + str(st)
            + " " + str(resp))
        print("regresion RED-1 OK:"
              " /history y /trust"
              " responden 200 via"
              " serve_combined")
    finally:
        srv.shutdown()
        srv.server_close()


def test_verification_verdict_signed(tmp_path) -> None:
    """AX-VERIF: enroll biometrico -> verify_face 1:1 -> veredicto firmado -> firma verificada offline."""
    import base64
    import json as _json
    import threading
    import time as _time
    import urllib.error
    import urllib.request
    from shared_engines.storage.database import SQLiteAdapter
    from shared_engines.common.clocks import FrozenClock
    from shared_engines.runtime.config import RuntimeConfig
    from shared_engines.runtime.kernel import ZyraKernel
    from shared_engines.runtime.capabilities import ZyraCapabilities
    from shared_engines.runtime.combined_api import serve_combined
    from shared_engines.verification.signatures import Ed25519Signer, Ed25519Verifier
    from shared_engines.security.biometrics import BiometricsEngine, BiometricsPolicy, DeterministicTestProvider, TemplateCipher
    from shared_engines.network.portable_profile import ProfileRegistry
    from shared_engines.audit.chain import AuditTrail
    from shared_engines.events.outbox import Outbox
    from shared_engines.common.serialization import canonical_json_dumps
    net_db = SQLiteAdapter(":memory:")
    signer, pub = Ed25519Signer.generate()
    kernel = ZyraKernel(db=net_db, clock=FrozenClock(), signer=signer, config=RuntimeConfig(host="127.0.0.1", port=0, api_token=None))
    kernel.bootstrap_root()
    kernel._biometrics = BiometricsEngine(db=net_db, clock=FrozenClock(), audit=kernel.audit, provider=DeterministicTestProvider(), cipher=TemplateCipher(master_key_hex="ab" * 32), policy=BiometricsPolicy(require_liveness=False, doc_reject=0.01, doc_review=0.02, doc_auto=0.03, dup_reject=0.98))
    caps = ZyraCapabilities(net_db, FrozenClock(), identity=kernel.identity, signer=signer)
    caps.profiles = ProfileRegistry(net_db, FrozenClock(), audit=AuditTrail(net_db, FrozenClock()), outbox=Outbox(net_db, FrozenClock()))
    caps.profiles.register_app(app_id="banco-ny", display_name="Banco NY", scopes=("display_name", "national_id", "id_country", "id_type", "id_number", "nationality", "birth_date", "address"))
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
        selfie = base64.b64encode(b"selfie-pedro-real").decode("ascii")
        docimg = selfie
        st, r1 = post("/identity/enroll", {"kind": "person", "display_name": "Pedro Prueba", "actor": "banco-ny", "doc_image_b64": docimg, "selfie_image_b64": selfie})
        assert st in (200, 201), str(st) + " " + str(r1)
        zid = ((r1.get("data") or {}).get("identity") or {}).get("zid")
        assert zid, str(r1)[:300]
        reg = caps.profiles
        reg.set_field(zid=zid, field="display_name", value="Pedro Prueba", verified=True)
        reg.set_field(zid=zid, field="id_country", value="SV", verified=True)
        reg.set_field(zid=zid, field="id_type", value="dui", verified=True)
        reg.set_field(zid=zid, field="birth_date", value="1992-04-04", verified=True)
        st, r2 = post("/verification/person", {"zid": zid, "selfie_b64": selfie, "actor_app": "banco-ny"})
        assert st == 200, str(st) + " " + str(r2)[:400]
        d = r2["data"]
        assert d["verified_person"] is True, str(d)[:200]
        assert d["fields"]["id_type"] == "dui"
        assert d["age"] >= 30
        assert d.get("signature")
        verde = bytes.fromhex(d["signature"])
        sin_firma = dict((k, v) for k, v in d.items() if k != "signature")
        recom = canonical_json_dumps(sin_firma).encode("utf-8")
        assert (lambda _s: Ed25519Verifier(_s.load_pem_private_key(pub, password=None).public_key().public_bytes(_s.Encoding.PEM, _s.PublicFormat.SubjectPublicKeyInfo)).verify(recom, verde))(__import__("cryptography.hazmat.primitives.serialization", fromlist=["serialization"])) is True  # F15-PUBKEY
        print("OK AX-VERIF: veredicto firmado, verificable offline")
    finally:
        srv.shutdown()
        srv.server_close()

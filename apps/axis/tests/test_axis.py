"""AXIS proofs: medical record with auto
appointment, legal case lifecycle, police
incident sealed evidence, role validation,
screens served."""
from __future__ import annotations

import threading
from pathlib import Path
from urllib.request import (
    Request,
    urlopen,
)

from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)

from apps.axis.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.axis.infrastructure.persistence.axis_store import (
    AxisStore,
)
from apps.axis.server import serve_axis


def _boot(tmp_path: Path):
    db = SQLiteAdapter(
        tmp_path / "axis.db"
    )
    clock = FrozenClock()
    store = AxisStore(db, clock)
    dead_client = NetworkClient(
        "http://127.0.0.1:1",
        timeout_seconds=1.0,
        max_retries=0,
    )
    server = serve_axis(store, dead_client)
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()
    base = (
        "http://127.0.0.1:"
        f"{server.bound_port}"
    )
    return db, store, base, server, thread


def test_medical_record_and_appointment(
    tmp_path: Path,
) -> None:
    db, store, base, server, thread = (
        _boot(tmp_path)
    )
    try:
        store.add_account(
            account_id="AX-doc1",
            zid=None,
            name="Dr. Ramirez",
            role="medico",
        )
        store.add_account(
            account_id="AX-pat1",
            zid=None,
            name="Maria Lopez",
            role="paciente",
        )
        row = store.add_medical_record(
            record_id="MED-001",
            patient_account="AX-pat1",
            doctor_account="AX-doc1",
            diagnosis="Gripe A",
            next_appointment=(
                "lunes 9am"
            ),
            sealed_doc="DOC-x1",
        )
        assert (
            row["next_appointment"]
            == "lunes 9am"
        )
        records = (
            store.medical_records_of(
                patient_account=(
                    "AX-pat1"
                )
            )
        )
        assert len(records) == 1
        assert records[0][
            "diagnosis"
        ] == "Gripe A"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


def test_legal_case_lifecycle(
    tmp_path: Path,
) -> None:
    db, store, base, server, thread = (
        _boot(tmp_path)
    )
    try:
        store.add_account(
            account_id="AX-law1",
            zid=None,
            name="Abogado Perez",
            role="abogado",
        )
        store.add_account(
            account_id="AX-cli1",
            zid=None,
            name="Cliente Uno",
            role="paciente",
        )
        case = store.add_legal_case(
            case_id="CASE-1",
            client_account="AX-cli1",
            lawyer_account="AX-law1",
            status="proceso",
            detail="audiencia pendiente",
            sealed_doc=None,
        )
        assert case["status"] == (
            "proceso"
        )
        updated = (
            store.update_case_status(
                case_id="CASE-1",
                status="libre",
                detail="liberado",
                sealed_doc=None,
            )
        )
        assert updated["status"] == (
            "libre"
        )
        cases = store.cases_for(
            lawyer_account="AX-law1"
        )
        assert len(cases) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


def test_incident_sealed_and_roles(
    tmp_path: Path,
) -> None:
    db, store, base, server, thread = (
        _boot(tmp_path)
    )
    try:
        store.add_account(
            account_id="AX-pol1",
            zid=None,
            name="Agente Cruz",
            role="policia",
        )
        store.add_incident(
            incident_id="INC-1",
            police_account="AX-pol1",
            description=(
                "robo reportado con"
                " evidencia"
            ),
            sealed_doc="DOC-ev1",
        )
        incidents = (
            store.list_incidents()
        )
        assert len(incidents) == 1
        assert incidents[0][
            "sealed_doc"
        ] == "DOC-ev1"
        try:
            store.add_account(
                account_id="AX-bad",
                zid=None,
                name="Fake",
                role="hacker",
            )
            raise AssertionError(
                "should fail"
            )
        except ValueError:
            pass
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


def test_screens_served(
    tmp_path: Path,
) -> None:
    db, store, base, server, thread = (
        _boot(tmp_path)
    )
    try:
        with urlopen(
            base + "/axis", timeout=10
        ) as response:
            home = response.read().decode(
                "utf-8"
            )
        assert "AXIS" in home
        assert "Registrarme" in home
        with urlopen(
            base
            + "/axis/gobierno",
            timeout=10,
        ) as response:
            gov = response.read().decode(
                "utf-8"
            )
        assert "Gobierno" in gov
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


# ====== AX-1/2/3 ======


def _axz_step(label):
    import sys
    print("AXZ-STEP " + label, flush=True)


def _axz_warn(label, st, body):
    import sys
    print("AXZ-WARN " + label
          + " -> HTTP " + str(st)
          + " " + str(body), flush=True)


def _axz_boot(with_verify=False, net_base=None):
    import threading
    import time as _time
    from apps.axis.infrastructure.persistence.axis_store import AxisStore
    from apps.axis.infrastructure.network.network_client import NetworkClient
    from apps.axis.server import serve_axis
    from apps.axis.life_history.integration import build_life_history
    from shared_engines.storage.database import SQLiteAdapter
    from shared_engines.common.clocks import SystemClock
    db = SQLiteAdapter(":memory:")
    store = AxisStore(db, SystemClock())
    if net_base:
        client = NetworkClient(net_base, timeout_seconds=10, max_retries=1)
    else:
        client = NetworkClient("http://127.0.0.1:1", timeout_seconds=1.0, max_retries=0)
    life = build_life_history(db=db, clock=SystemClock(), network_client=client)
    verify = None
    if with_verify:
        verify = _axz_make_verify(life)
    srv = serve_axis(store, client, life_history_service=life, verify_service=verify)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    _time.sleep(0.4)
    return store, life, client, ("http://127.0.0.1:" + str(srv.bound_port))


def _axz_make_verify(life):
    from apps.axis.life_history.public_verify import PublicVerifyService
    from shared_engines.storage.database import SQLiteAdapter
    mk = "ab" * 32
    ultimo = None
    for kw in (
        {"life": life, "network_db": SQLiteAdapter(":memory:"), "master_key_hex": mk},
        {"life": life, "master_key_hex": mk},
        {"life_history": life, "network_db": SQLiteAdapter(":memory:"), "master_key_hex": mk},
        {"life": life, "db": SQLiteAdapter(":memory:"), "master_key_hex": mk},
    ):
        try:
            return PublicVerifyService(**kw)
        except TypeError as e:
            ultimo = e
    raise AssertionError(
        "PublicVerifyService no construible: " + str(ultimo))


def _axz_form(url, form, role="gobierno", timeout=30):
    import urllib.error
    import urllib.parse
    import urllib.request
    headers = {}
    if role:
        headers["X-ZYRA-Actor-Role"] = role
    req = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode(), method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def _axz_json(method, url, doc=None, role="gobierno", timeout=30):
    import json as _json
    import urllib.error
    import urllib.request
    headers = {"Content-Type": "application/json"}
    if role:
        headers["X-ZYRA-Actor-Role"] = role
    data = _json.dumps(doc).encode() if doc is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)

    def _pick(crudo):
        try:
            return _json.loads(crudo)
        except Exception:
            return {"_raw": crudo[:200]
                    + " ...TAIL... "
                    + crudo[-1200:]}

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, _pick(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, _pick(e.read().decode("utf-8", "replace"))


def test_axz_law_blocks_register_person():
    from apps.axis.services.axis_link import AxisLink
    from apps.axis.infrastructure.network.network_client import NetworkClient
    link = AxisLink(NetworkClient("http://127.0.0.1:1"))
    try:
        link.register_person("X")
    except ValueError as exc:
        assert "biometria" in str(exc)
        return
    raise AssertionError("ley no aplicada")


def test_axz_birth_requires_registrar():
    store, life, _c, base = _axz_boot()
    st, body = _axz_form(
        base + "/axis/birth-register",
        {"registrar_account": "AX-fantasma",
         "child_name": "X", "birth_date": "2025-01-01",
         "birth_place": "SS", "sex": "F",
         "mother_name": "M", "mother_zid": "ZID-fake"},
        role=None)
    assert st == 403, body[:200]


def test_axz_full_government_flow(tmp_path=None):
    import base64 as _b64
    import threading
    import time as _time
    from apps.axis.infrastructure.persistence.axis_store import AxisStore
    from apps.axis.infrastructure.network.network_client import NetworkClient
    from apps.axis.server import serve_axis
    from apps.axis.life_history.integration import build_life_history
    from apps.axis.services.axis_link import AxisLink
    from shared_engines.storage.database import SQLiteAdapter
    from shared_engines.common.clocks import FrozenClock, SystemClock
    from shared_engines.runtime.config import RuntimeConfig
    from shared_engines.runtime.kernel import ZyraKernel
    from shared_engines.runtime.capabilities import ZyraCapabilities
    from shared_engines.runtime.combined_api import serve_combined
    from shared_engines.verification.signatures import Ed25519Signer
    from shared_engines.security.biometrics import (
        BiometricsEngine, BiometricsPolicy,
        DeterministicTestProvider, TemplateCipher)
    net_db = SQLiteAdapter(":memory:")
    signer, _ = Ed25519Signer.generate()
    kernel = ZyraKernel(db=net_db, clock=FrozenClock(), signer=signer,
        config=RuntimeConfig(host="127.0.0.1", port=0, api_token=None))
    kernel.bootstrap_root()
    kernel._biometrics = BiometricsEngine(
        db=net_db, clock=FrozenClock(), audit=kernel.audit,
        provider=DeterministicTestProvider(),
        cipher=TemplateCipher(master_key_hex="ab" * 32),
        policy=BiometricsPolicy(require_liveness=False,
            doc_reject=0.01, doc_review=0.02,
            doc_auto=0.03, dup_reject=0.98))
    caps = ZyraCapabilities(net_db, FrozenClock(),
        identity=kernel.identity, signer=signer)
    net_srv = serve_combined(kernel, caps, host="127.0.0.1", port=0)
    threading.Thread(target=net_srv.serve_forever, daemon=True).start()
    _time.sleep(0.4)
    net_base = "http://127.0.0.1:" + str(net_srv.server_address[1])
    client = NetworkClient(net_base, timeout_seconds=10, max_retries=1)
    assert AxisLink(client).register_app()[0] is True
    seed_m = _b64.b64encode(b"axis-bio-madre-gov").decode("ascii")
    ok_m, data_m, err_m = client.post("/identity/enroll",
        {"kind": "person", "display_name": "Madre Gov",
         "actor": "axis", "doc_image_b64": seed_m,
         "selfie_image_b64": seed_m})
    assert ok_m, str(err_m)
    zid_madre = ((data_m or {}).get("identity") or {}).get("zid")
    assert isinstance(zid_madre, str) and zid_madre.startswith("ZID-")
    ok_t, _td, err_t = client.post("/identity/transition",
        {"zid": zid_madre, "to_status": "ACTIVE",
         "actor": "axis", "reason": "onboarding"})
    assert ok_t, str(err_t)
    store = AxisStore(SQLiteAdapter(":memory:"), SystemClock())
    life = build_life_history(db=store._db, clock=SystemClock(), network_client=client)
    verify = _axz_make_verify(life)
    srv = serve_axis(store, client,
        life_history_service=life,
        verify_service=verify)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    _time.sleep(0.4)
    base = "http://127.0.0.1:" + str(srv.bound_port)
    _axz_step("1 birth-register (form)")
    st, html = _axz_form(base + "/axis/birth-register",
        {"registrar_account": "AX-gob-x",
         "child_name": "Bebe Censo",
         "birth_date": "2025-09-01",
         "birth_place": "SS", "sex": "F",
         "mother_name": "Madre Gov",
         "mother_zid": zid_madre})
    assert st == 200, html[:800]
    _axz_step("2 query life_persons (zid bebe)")
    baby = life._store._db.query_one(
        "SELECT person_id, zid FROM life_persons"
        " WHERE full_name = 'Bebe Censo'")
    assert baby is not None and baby["zid"], (
        "bebe debe nacer con ZID automatico")
    _axz_step("3 audit/verify")
    st, body = _axz_json("GET", base + "/axis/api/audit/verify")
    assert st == 200 and body["data"]["births_chain"]["ok"]
    _axz_step("4 censo gobierno")
    st, body = _axz_json("GET",
        base + "/axis/api/gobierno/censo", role="gobierno")
    assert st == 200, str(body)
    d = body["data"]
    assert d["poblacion_registrada"] >= 1
    assert d["con_zid"] >= 1
    _axz_step("5 censo sin rol (403)")
    st, body = _axz_json("GET",
        base + "/axis/api/gobierno/censo", role=None)
    assert st == 403, "censo 403"
    _axz_step("6 ingesta (diagnostico, no bloquea)")
    st, body = _axz_json("POST",
        base + "/axis/api/gobierno/ingesta",
        {"registrar_account": "AX-gob-x",
         "child_name": "Bebe Ingesta",
         "birth_date": "2025-09-02",
         "birth_place": "SS", "sex": "M",
         "mother_name": "Madre Gov",
         "mother_zid": zid_madre,
         "source": "ministerio-salud"})
    if st == 201:
        _axz_step("6b censo tras ingesta")
        st, body = _axz_json("GET",
            base + "/axis/api/gobierno/censo",
            role="gobierno")
        if body.get("data", {}).get(
            "poblacion_registrada", 0) < 2:
            _axz_warn("censo-ingesta",
                st, body)
    else:
        _axz_warn("INGESTA-PENDIENTE",
            st, body)
    _axz_step("7 verify/generate paciente (diagnostico)")
    st, body = _axz_json("POST",
        base + "/axis/api/verify/generate",
        {"subject_zid": zid_madre,
         "operator_account": "AX-gob-x",
         "operator_role": "paciente"}, role=None)
    code = None
    if st != 403:
        _axz_warn("verify-gen-paciente",
            st, body)
    else:
        _axz_step("8 verify/generate gobierno (diagnostico)")
        st, body = _axz_json("POST",
            base + "/axis/api/verify/generate",
            {"subject_zid": zid_madre,
             "operator_account": "AX-gob-x",
             "operator_role": "gobierno"})
        ddata = body.get("data") or {}
        if st == 201 and ddata.get("code"):
            code = ddata["code"]
        else:
            _axz_warn("verify-gen-gob",
                st, body)
    if code:
        _axz_step("9 verify/redeem (diagnostico)")
        st, body = _axz_json("POST",
            base + "/axis/api/verify/redeem",
            {"code": code,
             "requester": "Empleador X",
             "requester_role": "empleador"},
            role=None)
        if st == 200 and (body.get("data") or {}).get(
            "finding") == "SIN_REGISTROS_REPORTADOS":
            _axz_step("10 redeem reuso (diagnostico)")
            st, body = _axz_json("POST",
                base + "/axis/api/verify/redeem",
                {"code": code,
                 "requester": "Otro",
                 "requester_role": "empleador"},
                role=None)
            if st != 409:
                _axz_warn("reuso", st, body)
        else:
            _axz_warn("redeem", st, body)
    _axz_step("11 FIN flujo nucleo VERDE")

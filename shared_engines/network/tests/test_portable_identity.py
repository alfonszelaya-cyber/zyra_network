"""Portable identity proofs: register in one app,
recognized in another; scoped visibility; audited
access; verified levels."""
from __future__ import annotations

from pathlib import Path

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
from shared_engines.network.portable_profile import (
    LEVEL_SELF,
    LEVEL_VERIFIED,
    ProfileRegistry,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)
from shared_engines.telemetry.collector import (
    TelemetryCollector,
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
            "network.profile.updated",
            "network.profile.accessed",
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
        self.telemetry = TelemetryCollector(
            self.db, self.clock
        )

    def close(self) -> None:
        self.db.close()


def test_register_once_recognized_everywhere(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="nexo",
            display_name="NEXO",
            scopes=(
                "display_name",
                "contact",
            ),
        )
        net.profiles.register_app(
            app_id="subastas",
            display_name="Subastas",
            scopes=("display_name",),
        )
        user = (
            net.identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name="maria",
                actor="nexo",
            )
        )
        net.profiles.set_field(
            zid=user.zid,
            field="display_name",
            value="Maria Lopez",
        )
        net.profiles.set_field(
            zid=user.zid,
            field="contact",
            value="maria@zyra.sv",
        )
        view_nexo = (
            net.profiles.view_for_app(
                app_id="nexo",
                zid=user.zid,
            )
        )
        assert (
            view_nexo.fields[
                "display_name"
            ]
            == "Maria Lopez"
        )
        assert (
            view_nexo.fields["contact"]
            == "maria@zyra.sv"
        )
        view_sub = (
            net.profiles.view_for_app(
                app_id="subastas",
                zid=user.zid,
            )
        )
        assert (
            view_sub.fields[
                "display_name"
            ]
            == "Maria Lopez"
        )
        assert "contact" not in (
            view_sub.fields
        )
    finally:
        net.close()


def test_unregistered_app_denied(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        user = (
            net.identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name="luis",
                actor="t",
            )
        )
        try:
            net.profiles.view_for_app(
                app_id="malware",
                zid=user.zid,
            )
            raise AssertionError(
                "expected"
                " PermissionError"
            )
        except PermissionError:
            pass
    finally:
        net.close()


def test_verified_level_and_telemetry(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="gov",
            display_name="Gov",
            scopes=("national_id",),
        )
        user = (
            net.identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name="ana",
                actor="t",
            )
        )
        net.profiles.set_field(
            zid=user.zid,
            field="national_id",
            value="XXXXXXXXXX",
            verified=True,
        )
        view = net.profiles.view_for_app(
            app_id="gov", zid=user.zid
        )
        assert (
            view.levels["national_id"]
            == LEVEL_VERIFIED
        )
        assert (
            view.levels["national_id"]
            != LEVEL_SELF
        )
        net.telemetry.ingest_outbox(
            net.outbox
        )
        accessed = (
            net.telemetry.query_events(
                event_type=(
                    "network.profile"
                    ".accessed"
                )
            )
        )
        assert len(accessed) >= 1
    finally:
        net.close()


def test_audit_trail_records_access(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="a1",
            display_name="A1",
            scopes=("display_name",),
        )
        user = (
            net.identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name="b",
                actor="t",
            )
        )
        net.profiles.set_field(
            zid=user.zid,
            field="display_name",
            value="B",
        )
        net.profiles.view_for_app(
            app_id="a1", zid=user.zid
        )
        count = net.audit.verify()
        assert count >= 1
    finally:
        net.close()


def test_universal_id_maria_and_juan(
    tmp_path,
) -> None:
    """AX-ID: Maria (Guatemala,
    pasaporte) y Juan (El Salvador,
    DUI) - campos tipados, edad
    derivada, niveles, audit."""
    from shared_engines.network.portable_profile import (
        ProfileRegistry)
    from shared_engines.audit.chain import (
        AuditTrail)
    from shared_engines.events.outbox import (
        Outbox)
    from shared_engines.events.contracts import (
        EventCatalog)
    from shared_engines.storage.database import (
        SQLiteAdapter)
    from shared_engines.common.clocks import (
        FrozenClock)
    db = SQLiteAdapter(
        tmp_path / "id.db")
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    cat = EventCatalog()
    for et in (
        "network.profile.updated",
        "network.profile.accessed",
    ):
        cat.register(et)
    reg = ProfileRegistry(
        db, clock, audit=audit,
        outbox=outbox)
    reg.register_app(
        app_id="banco-ny",
        display_name="Banco NY",
        scopes=(
            "display_name",
            "national_id",
            "id_country",
            "id_type",
            "id_number",
            "nationality",
            "birth_date",
            "address",
        ),
    )
    mzid = ("ZID-maria-gt-"
            "000000000001")
    reg.set_field(
        zid=mzid,
        field="display_name",
        value="Maria Perez",
        verified=True)
    reg.set_field(
        zid=mzid,
        field="id_country",
        value="GT", verified=True)
    reg.set_field(
        zid=mzid,
        field="id_type",
        value="passport",
        verified=True)
    reg.set_field(
        zid=mzid,
        field="id_number",
        value="GT-PASS-8842",
        verified=True)
    reg.set_field(
        zid=mzid,
        field="nationality",
        value="GT", verified=True)
    reg.set_field(
        zid=mzid,
        field="birth_date",
        value="1998-03-15",
        verified=True)
    reg.set_field(
        zid=mzid,
        field="address",
        value="Guatemala")
    jzid = ("ZID-juan-sv-"
            "000000000001")
    reg.set_field(
        zid=jzid,
        field="display_name",
        value="Juan Lopez",
        verified=True)
    reg.set_field(
        zid=jzid,
        field="id_country",
        value="SV", verified=True)
    reg.set_field(
        zid=jzid,
        field="id_type",
        value="dui", verified=True)
    reg.set_field(
        zid=jzid,
        field="id_number",
        value="00000000-0",
        verified=True)
    reg.set_field(
        zid=jzid,
        field="nationality",
        value="SV", verified=True)
    reg.set_field(
        zid=jzid,
        field="birth_date",
        value="1990-06-01",
        verified=True)
    v = reg.universal_view(
        app_id="banco-ny",
        zid=mzid)
    assert (v["fields"]
            ["id_country"]
            == "GT"), str(v)
    assert (v["fields"]
            ["id_type"]
            == "passport")
    assert v["age"] >= 24, str(v)
    assert (v["levels"]
            ["id_number"]
            == "VERIFIED")
    assert (v["levels"]
            ["address"]
            == "SELF_DECLARED")
    vj = reg.universal_view(
        app_id="banco-ny",
        zid=jzid)
    assert (vj["fields"]
            ["id_type"]
            == "dui")
    assert (vj["fields"]
            ["id_country"]
            == "SV")
    assert vj["age"] >= 33
    print("OK AX-ID: Maria GT pasaporte"
          " y Juan SV DUI - edad derivada"
          " y niveles correctos")


def test_consent_and_freeze_flow(tmp_path) -> None:
    """AX-CONSENT/FREEZE: otorgar con biometria -> expiracion -> revocacion; freeze bloquea verdict; unfreeze solo con codigo."""
    from shared_engines.network.portable_profile import ProfileRegistry, FrozenIdentityError
    from shared_engines.audit.chain import AuditTrail
    from shared_engines.events.outbox import Outbox
    from shared_engines.events.contracts import EventCatalog
    from shared_engines.storage.database import SQLiteAdapter
    from shared_engines.common.clocks import SystemClock
    db = SQLiteAdapter(tmp_path / "cf.db")
    clock = SystemClock()
    reg = ProfileRegistry(db, clock, audit=AuditTrail(db, clock), outbox=Outbox(db, clock))
    zid = "ZID-fraud-test-00000001"
    reg.set_field(zid=zid, field="display_name", value="Pedro", verified=True)
    reg.register_app(app_id="banco", display_name="Banco", scopes=("display_name", "national_id"))
    c = reg.grant_consent(zid=zid, app_id="banco", fields=("display_name", "national_id"), face_score=0.92, ttl_hours=24.0)
    assert c["consent_id"].startswith("CON-")
    campos = reg.check_consent(zid=zid, app_id="banco")
    assert campos is not None and "display_name" in campos
    db.execute("UPDATE profile_consents SET expires_at = 1")
    assert reg.check_consent(zid=zid, app_id="banco") is None
    c2 = reg.grant_consent(zid=zid, app_id="banco", fields=("display_name",), face_score=0.92)
    reg.revoke_consent(zid=zid, consent_id=c2["consent_id"])
    assert reg.check_consent(zid=zid, app_id="banco") is None
    res = reg.freeze_zid(zid=zid, reason="robo de telefono")
    assert res["unfreeze_code"]
    congelado = False
    try:
        reg.verification_verdict(app_id="banco", zid=zid, face_verdict={"match": True, "score": 0.95}, signer=None, clock=clock)
    except FrozenIdentityError:
        congelado = True
    assert congelado, "freeze no bloqueo"
    assert reg.is_frozen(zid=zid)
    assert reg.unfreeze_zid(zid=zid, code="000000") is False
    assert reg.unfreeze_zid(zid=zid, code=res["unfreeze_code"]) is True
    assert not reg.is_frozen(zid=zid)
    lista = reg.consents_of(zid=zid)
    assert len(lista) >= 2
    print("OK AX-CONSENT/FREEZE: otorgar, expirar, revocar, congelar, desbloquear con codigo, historial visible")


def test_expediente_legal_pedro(tmp_path) -> None:
    """AX-EXP: Pedro con DUI (SV) + pasaporte (US) en el MISMO ZID. Assurance L2->L4->L5. Revocacion en historial."""
    from shared_engines.network.portable_profile import (
        ProfileRegistry)
    from shared_engines.audit.chain import AuditTrail
    from shared_engines.events.outbox import Outbox
    from shared_engines.events.contracts import EventCatalog
    from shared_engines.storage.database import SQLiteAdapter
    from shared_engines.common.clocks import FrozenClock
    from shared_engines.runtime.config import RuntimeConfig
    from shared_engines.runtime.kernel import ZyraKernel
    from shared_engines.verification.signatures import Ed25519Signer
    from shared_engines.security.biometrics import BiometricsEngine, BiometricsPolicy, DeterministicTestProvider, TemplateCipher
    db = SQLiteAdapter(tmp_path / "exp.db")
    clock = FrozenClock()
    signer, _ = Ed25519Signer.generate()
    kernel = ZyraKernel(db=db, clock=clock, signer=signer, config=RuntimeConfig(host="127.0.0.1", port=0, api_token=None))
    kernel.bootstrap_root()
    kernel._biometrics = BiometricsEngine(db=db, clock=clock, audit=kernel.audit, provider=DeterministicTestProvider(), cipher=TemplateCipher(master_key_hex="ab" * 32), policy=BiometricsPolicy(require_liveness=False, doc_reject=0.01, doc_review=0.02, doc_auto=0.03, dup_reject=0.98))
    reg = ProfileRegistry(db, clock, audit=AuditTrail(db, clock), outbox=Outbox(db, clock))
    zid = "ZID-pedro-exp-00000001"
    reg.set_field(zid=zid, field="display_name", value="Pedro Prueba", verified=True)
    a0 = reg.assurance_level(zid=zid)
    assert a0["assurance_level"] == 0, str(a0)
    d1 = reg.add_document(zid=zid, doc_type="dui", doc_number="00000000-0", issuing_country="SV", issuing_authority="RNPN", issue_date="2015-01-01", expiry_date="2025-01-01", verified=True, verified_by="RNPN")
    assert d1["document_id"].startswith("DOCX-")
    a2 = reg.assurance_level(zid=zid)
    assert a2["assurance_level"] == 2, str(a2)
    db.execute("INSERT INTO biometric_templates (template_id, identity_zid, modality, template_enc, dims, created_at, case_id, template_sha) VALUES ('T-1', ?, 'face', x'00', 1, 1, 'CASE-EXP-1', 'X')", (zid,))
    a4 = reg.assurance_level(zid=zid)
    assert a4["assurance_level"] == 4, str(a4)
    d2 = reg.add_document(zid=zid, doc_type="passport", doc_number="US-PASS-777", issuing_country="US", issuing_authority="U.S. Department of State", issue_date="2024-01-01", expiry_date="2034-01-01", verified=True, verified_by="U.S. Dept of State")
    a5 = reg.assurance_level(zid=zid)
    assert a5["assurance_level"] == 5, str(a5)
    assert a5["countries"] == ["SV", "US"], str(a5)
    docs = reg.list_documents(zid=zid)
    assert len(docs) == 2
    tipos = sorted(d["doc_type"] for d in docs)
    assert tipos == ["dui", "passport"], str(tipos)
    reg.revoke_document(zid=zid, document_id=d2["document_id"], reason="perdida")
    docs2 = reg.list_documents(zid=zid)
    rev = [d for d in docs2 if d["document_id"] == d2["document_id"]]
    assert rev[0]["status"] == "REVOKED"
    a6 = reg.assurance_level(zid=zid)
    assert a6["assurance_level"] == 4, str(a6)
    print("OK AX-EXP: Pedro SV-DUI + US-pasaporte en un ZID, assurance 0->2->4->5, revocacion en historial")


def test_full_legal_view_consular(
    tmp_path,
) -> None:
    """RED-EXP-2: vista legal
    completa para consulados:
    frescura por campo, ciclo de
    vida de documentos, assurance,
    consentimientos, congelamiento."""
    from shared_engines.network.portable_profile import (
        ProfileRegistry)
    from shared_engines.audit.chain import (
        AuditTrail)
    from shared_engines.events.outbox import (
        Outbox)
    from shared_engines.storage.database import (
        SQLiteAdapter)
    from shared_engines.common.clocks import (
        FrozenClock)
    from shared_engines.runtime.config import (
        RuntimeConfig)
    from shared_engines.runtime.kernel import (
        ZyraKernel)
    from shared_engines.verification.signatures import (
        Ed25519Signer)
    from shared_engines.security.biometrics import (
        BiometricsEngine, BiometricsPolicy,
        DeterministicTestProvider, TemplateCipher)
    db = SQLiteAdapter(
        tmp_path / "exp2.db")
    clock = FrozenClock()
    signer, _ = Ed25519Signer.generate()
    kernel = ZyraKernel(
        db=db, clock=clock,
        signer=signer,
        config=RuntimeConfig(
            host="127.0.0.1", port=0,
            api_token=None))
    kernel.bootstrap_root()
    kernel._biometrics = BiometricsEngine(
        db=db, clock=clock,
        audit=kernel.audit,
        provider=DeterministicTestProvider(),
        cipher=TemplateCipher(
            master_key_hex="ab" * 32),
        policy=BiometricsPolicy(
            require_liveness=False,
            doc_reject=0.01,
            doc_review=0.02,
            doc_auto=0.03,
            dup_reject=0.98))
    reg = ProfileRegistry(
        db, clock,
        audit=AuditTrail(db, clock),
        outbox=Outbox(db, clock))
    reg.register_app(
        app_id="consulado-sv",
        display_name="Consulado SV",
        scopes=("display_name",
                "id_country"))
    zid = "ZID-exp2-00000001"
    reg.set_field(
        zid=zid, field="display_name",
        value="Pedro Exp2",
        verified=True)
    reg.set_field(
        zid=zid, field="id_country",
        value="SV", verified=True)
    reg.set_field(
        zid=zid, field="id_type",
        value="dui", verified=True)
    reg.set_field(
        zid=zid, field="birth_date",
        value="1992-04-04",
        verified=True)
    reg.add_document(
        zid=zid, doc_type="dui",
        doc_number="00000000-0",
        issuing_country="SV",
        verified=True,
        verified_by="RNPN")
    d2 = reg.add_document(
        zid=zid, doc_type="passport",
        doc_number="US-PASS-9",
        issuing_country="US",
        verified=True,
        verified_by="StateDept")
    reg.revoke_document(
        zid=zid,
        document_id=d2["document_id"],
        reason="perdida")
    reg.grant_consent(
        zid=zid,
        app_id="consulado-sv",
        fields=("display_name",
                "id_country"),
        face_score=0.99)
    vista = reg.full_legal_view(
        zid=zid)
    assert vista["zid"] == zid, (
        str(vista)[:200])
    assert len(
        vista["identity_fields"]) == 4
    for f in vista["identity_fields"]:
        assert "age_seconds" in f
        assert "level" in f
    docs = vista["documents"]
    assert len(docs) == 2
    estados = sorted(
        d["status"] for d in docs)
    assert estados == [
        "REVOKED", "VALID"], str(estados)
    ls = vista["legal_summary"]
    assert ls["revoked_documents"] == 1
    assert ls["verified_documents"] == 1
    assert (vista["assurance"]
            ["assurance_level"] == 2), (
        str(vista["assurance"]))
    assert len(vista["consents"]) >= 1
    assert vista["frozen"] is False
    assert vista["generated_at"] > 0
    print("OK RED-EXP-2: full_legal_view"
          " con frescura por campo,"
          " ciclo de vida, assurance,"
          " consentimientos y congelamiento")

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

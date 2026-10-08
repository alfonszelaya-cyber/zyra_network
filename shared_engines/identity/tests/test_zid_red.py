import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.identity.guardian_engine import (
    GuardianEngine)
from shared_engines.identity.birth_registry_engine import (
    BirthRegistryEngine)
from shared_engines.identity.minor_biometrics_engine import (
    MinorBiometricsEngine)
from shared_engines.identity.representation_engine import (
    RepresentationEngine)


def test_r2_guardian_canonico(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "g.db")
    gl = GuardianEngine(db, FrozenClock())
    with pytest.raises(ValueError):
        gl.link(guardian_zid=" ",
                minor_zid="ZID-M", role="TUTOR")
    with pytest.raises(ValueError):
        gl.link(guardian_zid="ZID-P",
                minor_zid="ZID-M", role=" ")
    with pytest.raises(ValueError):
        gl.link(guardian_zid="ZID-P",
                minor_zid="ZID-M", role="TIO")
    with pytest.raises(ValueError):
        gl.link(guardian_zid="ZID-P",
                minor_zid="ZID-P", role="PADRE")
    l1 = gl.link(guardian_zid="ZID-PAPA",
        minor_zid="ZID-NINO", role="PADRE")
    assert l1["status"] == "activa"
    with pytest.raises(ValueError):
        gl.link(guardian_zid="ZID-PAPA",
            minor_zid="ZID-NINO", role="PADRE")
    l2 = gl.link(guardian_zid="ZID-PAPA",
        minor_zid="ZID-NINO", role="TUTOR")
    assert len(gl.guardians_of("ZID-NINO")) == 2
    assert len(gl.minors_of("ZID-PAPA")) == 2
    assert gl.is_guardian("ZID-PAPA",
                          "ZID-NINO") is True
    assert gl.is_guardian("ZID-PAPA", "ZID-NINO",
        role="MADRE") is False
    gl.revoke(l2["link_id"], reason="fin tutela")
    gl.revoke(l1["link_id"], reason="otro")
    assert gl.is_guardian("ZID-PAPA",
                          "ZID-NINO") is False
    with pytest.raises(ValueError):
        gl.revoke(l1["link_id"], reason="x")
    again = gl.link(guardian_zid="ZID-PAPA",
        minor_zid="ZID-NINO", role="PADRE")
    assert again["status"] == "activa"
    assert again.get("reactivated") is True
    print("OK R-2: vinculo canonico por ZIDs (regla 63) + UNIQUE rol activo + revocacion con motivo + re-activacion")


def test_r1_nacimiento_compone_red(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "b.db")
    br = BirthRegistryEngine(db, FrozenClock())
    with pytest.raises(ValueError):
        br.register_birth(child_name=" ",
            mother_zid="ZID-M")
    with pytest.raises(ValueError):
        br.register_birth(child_name="Nino",
            mother_zid=" ")
    with pytest.raises(ValueError):
        br.register_birth(child_name="X",
            mother_zid="ZID-M", sex="Q")
    b = br.register_birth(child_name="Nina Perez",
        mother_zid="ZID-MAMA",
        father_zid="ZID-PAPA",
        birth_date="2026-01-15", sex="F")
    assert b["cert_code"].startswith("ZCERT-")
    assert b["child_zid"] == ""
    assert b["life_seq"] is None
    g = br.get_birth(b["birth_id"])
    assert g["found"] is True
    assert g["mother_zid"] == "ZID-MAMA"
    with pytest.raises(ValueError):
        br.bind_existing_zid(b["birth_id"], zid=" ")
    z = br.bind_existing_zid(b["birth_id"],
        zid="ZID-NINA")
    assert z["child_zid"] == "ZID-NINA"
    with pytest.raises(ValueError):
        br.bind_existing_zid(b["birth_id"],
            zid="ZID-OTRO")
    with pytest.raises(KeyError):
        br.bind_existing_zid("NO", zid="ZID-X")


    class _FakeLife:
        def __init__(self):
            self.n = 0
        def append(self, **kw):
            self.n += 1

            class E:
                entry_seq = self.n
            return E()


    class _FakeIds:
        def register_identity(self, **kw):

            class I:
                zid = "ZID-FROM-ENGINE"
            return I()


    db2 = SQLiteAdapter(tmp_path / "b2.db")
    br2 = BirthRegistryEngine(
        db2, FrozenClock(),
        identity_engine=_FakeIds(),
        life_history=_FakeLife())
    b2 = br2.register_birth(child_name="Con Red",
        mother_zid="ZID-M2", sex="M")
    assert b2["child_zid"] == "ZID-FROM-ENGINE"
    assert b2["life_seq"] == 1
    print("OK R-1: capa civil fina + INTEGRA IdentityEngine (ZID real) y LifeHistory (birth_registration en la cadena de la Red) cuando se proveen; fallback fino documentado; bind unico regla 78")


def test_r4_biometria_menores_regla78(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "bi.db")
    gl = GuardianEngine(db, FrozenClock())
    gl.link(guardian_zid="ZID-TUTOR",
        minor_zid="ZID-NENE", role="TUTOR")
    bio = MinorBiometricsEngine(db, FrozenClock(),
        guardian_engine=gl)
    lc0 = bio.phase_of("ZID-NENE")
    assert lc0["phase"] == "PENDING_BIOMETRIC"
    with pytest.raises(ValueError):
        bio.enroll(zid="ZID-NENE", kind="HUELLA",
            template_b64="T1",
            guardian_zid="ZID-TUTOR",
            quality=500)
    with pytest.raises(ValueError):
        bio.enroll(zid="ZID-NENE", kind="HUELLA",
            template_b64="T1",
            guardian_zid="ZID-INTRUSO")
    en = bio.enroll(zid="ZID-NENE", kind="HUELLA",
        template_b64="T-NENE", quality=80,
        guardian_zid="ZID-TUTOR")
    assert len(en["template_hash"]) == 64
    assert bio.phase_of(
        "ZID-NENE")["phase"] == "ENROLADO"
    assert bio.verify(zid="ZID-NENE",
        kind="HUELLA",
        template_b64="T-NENE")["matched"] is True
    en2 = bio.enroll(zid="ZID-NENE",
        kind="HUELLA",
        template_b64="T-GRANDE",
        guardian_zid="ZID-TUTOR")
    st = {e["bio_id"]: e["status"]
          for e in bio.phase_of(
              "ZID-NENE")["entries"]}
    assert st[en["bio_id"]] == "reemplazada"
    assert st[en2["bio_id"]] == "activa"
    assert bio.revoke_all("ZID-NENE",
        reason="incidente")["revoked"] == 1
    assert bio.verify(zid="ZID-NENE",
        kind="HUELLA",
        template_b64="T-GRANDE")["matched"] \
        is False
    print("OK R-4: nace PENDING (regla 78) + enrolamiento EXIGE tutor activo del GuardianEngine (regla 69) + crecimiento (reemplazo) + revocacion total — ENCIMA del BiometricsEngine existente (regla 69)")


def test_r5_representacion_con_vinculo(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "r.db")
    gl = GuardianEngine(db, FrozenClock())
    gl.link(guardian_zid="ZID-TUT",
        minor_zid="ZID-MENOR", role="TUTOR")
    rep = RepresentationEngine(db, FrozenClock(),
        guardian_engine=gl)
    with pytest.raises(ValueError):
        rep.grant(guardian_zid="ZID-FAKE",
            minor_zid="ZID-MENOR",
            service="semilla.matricula")
    with pytest.raises(ValueError):
        rep.grant(guardian_zid="ZID-TUT",
            minor_zid="ZID-MENOR", service=" ")
    g = rep.grant(guardian_zid="ZID-TUT",
        minor_zid="ZID-MENOR",
        service="semilla.matricula")
    assert rep.can_act("ZID-TUT", "ZID-MENOR",
        "semilla.matricula") is True
    assert rep.can_act("ZID-TUT", "ZID-MENOR",
        "axis.salud") is False
    rep.grant(guardian_zid="ZID-TUT",
        minor_zid="ZID-MENOR", service="*")
    assert rep.can_act("ZID-TUT", "ZID-MENOR",
        "axis.salud") is True
    rep.revoke(g["rep_id"],
        reason="ajuste de alcance")
    assert rep.can_act("ZID-TUT", "ZID-MENOR",
        "semilla.matricula") is True
    assert rep.can_act("ZID-TUT", "ZID-MENOR",
        "semilla.matricula") is True
    assert len(rep.representations_of(
        "ZID-MENOR")) == 2
    print("OK R-5: representacion EXIGE vinculo (regla 66) + alcance por servicio y comodin + revocacion")


def test_r9_sesiones_firmas(tmp_path) -> None:
    from shared_engines.protocol.sessions.signatures_engine import (
        SessionSignatureEngine)
    db = SQLiteAdapter(tmp_path / "s.db")
    ss = SessionSignatureEngine(db, FrozenClock())
    with pytest.raises(ValueError):
        ss.open_session(zid=" ")
    s = ss.open_session(zid="ZID-1", app="semilla",
        ttl_seconds=100.0)
    assert s["status"] == "abierta"
    sg = ss.sign(s["session_id"],
        message="matricular a ZID-NENE")
    assert len(sg["seal"]) == 64
    with pytest.raises(ValueError):
        ss.sign(s["session_id"], message=" ")
    assert ss.verify(sg["sig_id"],
        message="matricular a ZID-NENE")["valid"] \
        is True
    assert ss.verify(sg["sig_id"],
        message="cambiado")["valid"] is False
    ss.close_session(s["session_id"])
    with pytest.raises(ValueError):
        ss.sign(s["session_id"], message="tardio")
    with pytest.raises(ValueError):
        ss.close_session(s["session_id"])
    assert len(ss.sessions_of("ZID-1")) == 1
    print("OK R-9: sesiones con TTL + firmas con sello verificable (alteracion detectada) + cierre terminal")

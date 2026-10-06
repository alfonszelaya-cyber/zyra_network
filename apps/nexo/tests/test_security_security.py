from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.security_identity.authorization_engine import NexoAuthorizationEngine
from apps.nexo.domain.security_identity.identity_engine import NexoIdentityRefEngine

def test_rbac_y_referencias(tmp_path):
    az = NexoAuthorizationEngine(
        SQLiteAdapter(tmp_path / "az.db"), FrozenClock())
    az.grant(company_id="EMP-S", actor="op",
        role="OPERATOR", max_amount="500")
    assert az.can(actor="op", company_id="EMP-S",
        role_needed="OPERATOR",
        amount="100")["allowed"] is True
    assert az.can(actor="op", company_id="EMP-S",
        role_needed="OPERATOR",
        amount="900")["allowed"] is False
    ir = NexoIdentityRefEngine(
        SQLiteAdapter(tmp_path / "ir.db"), FrozenClock())
    ref = ir.register_reference(zid="ZID-S-1",
        provider="RNPN",
        provider_reference="R-1",
        assurance_level="L5")
    assert "national_id" not in ref
    assert "dui" not in ref
    print("OK seguridad: RBAC tope monto + regla 63")

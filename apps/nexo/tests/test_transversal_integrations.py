from apps.nexo.services.transversal.currency.currency_gateway import NexoCurrencyGateway
from apps.nexo.services.transversal.finance.finance_gateway import NexoFinanceGateway
from apps.nexo.services.transversal.ai.ai_gateway import NexoAIGateway
from apps.nexo.services.transversal.verification.verification_gateway import NexoVerificationGateway
from apps.nexo.services.transversal.security.security_gateway import NexoSecurityGateway

def test_gateways_transversales_honestos():
    cur = NexoCurrencyGateway()
    assert (cur.convert("10", "USD",
                        "EUR")["converted"] == "9.20")
    assert (NexoFinanceGateway().capabilities()
            ["finance_master"] is False)
    assert (NexoAIGateway().classify_document(
        "compra de materiales")["category"]
        in ("compra", "pago"))
    assert (NexoVerificationGateway().mode
            == "not_configured")
    assert (NexoSecurityGateway().mode
            == "not_configured")
    print("OK transversal: 5 gateways operan honesto")

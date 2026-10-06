
from __future__ import annotations
from apps.nexo.domain.operations.operations_engine import (
    OperationsEngine)

class RegisterLogisticsCostUseCase:
    """Registra un costo logistico (flete, transporte,
    envio) como operacion contable de la empresa
    (regla 70: solo lo contable de la logistica vive
    en NEXO; el negocio logistico es de SUBASTAS)."""

    def __init__(self, operations):
        self._ops = operations

    def execute(self, *, company_id, description,
                amount, reference="", carrier="") \
                -> dict:
        op = self._ops.create_operation(
            company_id=company_id,
            operation_type="LOGISTICS_COST",
            description=description, amount=amount,
            metadata={"reference": reference,
                      "carrier": carrier})
        return {"operation_id":
                    op["operation_id"],
                "operation_number":
                    op["operation_number"],
                "amount": op["amount"],
                "operation_type":
                    op["operation_type"],
                "status": op["status"]}

"""AGRO operation matrix - additive module.

Maps every sensitive server operation to the
roles allowed to perform it, using AGRO's real
role constants (producer, company, government,
operator, administrator).

Note: agricultor/ganadero are producer_type
values; their role is PRODUCER. Banco maps to
COMPANY.

Enforced via the existing SecurityGateway +
SecurityContext. Self-contained tests.
"""
from __future__ import annotations

import unittest

from apps.agro.constants.roles.constants import (
    ADMINISTRATOR,
    COMPANY,
    GOVERNMENT,
    OPERATOR,
    PRODUCER,
)
from apps.agro.security.security_context import (
    SecurityContext,
)
from apps.agro.security.security_gateway import (
    SecurityGateway,
)

OPERATIONS = {
    "producers.register": (
        OPERATOR,
        ADMINISTRATOR,
    ),
    "producers.verify": (
        GOVERNMENT,
        ADMINISTRATOR,
    ),
    "production.register": (PRODUCER,),
    "aid.request": (PRODUCER,),
    "aid.eligibility": (GOVERNMENT,),
    "aid.approve": (GOVERNMENT,),
    "aid.assign": (GOVERNMENT,),
    "aid.deliver": (GOVERNMENT,),
    "aid.confirm": (PRODUCER,),
    "alerts.evaluate": (
        OPERATOR,
        ADMINISTRATOR,
    ),
    "events.emit": (
        PRODUCER,
        COMPANY,
        GOVERNMENT,
        OPERATOR,
        ADMINISTRATOR,
    ),
}


class OperationMatrix:
    def __init__(self) -> None:
        self._gateway = SecurityGateway()

    def check(
        self,
        *,
        operation: str,
        role: str,
        subject_id: str,
    ) -> bool:
        allowed = OPERATIONS.get(operation)
        if allowed is None:
            raise ValueError(
                "unknown operation: "
                + operation
            )
        return role in allowed

    def enforce(
        self,
        *,
        operation: str,
        role: str,
        subject_id: str,
    ) -> None:
        allowed = OPERATIONS.get(operation)
        if allowed is None:
            raise ValueError(
                "unknown operation: "
                + operation
            )
        if role not in allowed:
            raise PermissionError(
                "Permission denied:"
                " " + operation
                + " for role "
                + role
            )


class OperationMatrixTests(unittest.TestCase):
    def _matrix(self) -> OperationMatrix:
        return OperationMatrix()

    def test_producer_can_do_own_ops(
        self,
    ) -> None:
        matrix = self._matrix()
        self.assertTrue(
            matrix.check(
                operation=(
                    "production.register"
                ),
                role=PRODUCER,
                subject_id="PRD-1",
            )
        )
        self.assertTrue(
            matrix.check(
                operation="aid.request",
                role=PRODUCER,
                subject_id="PRD-1",
            )
        )
        self.assertTrue(
            matrix.check(
                operation="aid.confirm",
                role=PRODUCER,
                subject_id="PRD-1",
            )
        )

    def test_government_government_ops_only(
        self,
    ) -> None:
        matrix = self._matrix()
        for op in (
            "producers.verify",
            "aid.eligibility",
            "aid.approve",
            "aid.assign",
            "aid.deliver",
        ):
            self.assertTrue(
                matrix.check(
                    operation=op,
                    role=GOVERNMENT,
                    subject_id="GOV-1",
                )
            )
        self.assertFalse(
            matrix.check(
                operation="aid.approve",
                role=PRODUCER,
                subject_id="PRD-1",
            )
        )

    def test_producer_cannot_approve_aid(
        self,
    ) -> None:
        matrix = self._matrix()
        with self.assertRaises(
            PermissionError
        ):
            matrix.enforce(
                operation="aid.approve",
                role=PRODUCER,
                subject_id="PRD-1",
            )

    def test_unknown_operation_rejected(
        self,
    ) -> None:
        matrix = self._matrix()
        with self.assertRaises(ValueError):
            matrix.check(
                operation="hack.system",
                role=ADMINISTRATOR,
                subject_id="ADM-1",
            )

    def test_gateway_integration(
        self,
    ) -> None:
        context = SecurityContext(
            subject_id="GOV-1",
            roles={GOVERNMENT},
            permissions={"aid.approve"},
        )
        gateway = SecurityGateway()
        self.assertTrue(
            gateway.authorize(
                context, "aid.approve"
            )
        )
        with self.assertRaises(
            PermissionError
        ):
            gateway.authorize(
                context, "aid.deliver"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ---- additive PLUS: grupos y ops nuevas ----
STAFF_ROLES = frozenset({
    GOVERNMENT, OPERATOR, ADMINISTRATOR,
})
ANY_PRODUCER = frozenset({
    PRODUCER, GOVERNMENT, ADMINISTRATOR,
})

OPERATIONS.update({
    "land.create": ANY_PRODUCER,
    "machinery.create": ANY_PRODUCER,
    "inventory.create": ANY_PRODUCER,
    "water.create": ANY_PRODUCER,
    "unit.create": ANY_PRODUCER,
    "unit.close": ANY_PRODUCER,
    "profile.update": ANY_PRODUCER,
    "document.register": (PRODUCER,),
    "document.verify": STAFF_ROLES,
    "plan.create": ANY_PRODUCER,
    "plan.advance": ANY_PRODUCER,
    "plan.cancel": ANY_PRODUCER,
    "plan.cost.add": ANY_PRODUCER,
    "incident.report": ANY_PRODUCER,
    "incident.resolve": STAFF_ROLES,
    "sale.create": (
        PRODUCER, COMPANY, GOVERNMENT,
        ADMINISTRATOR,
    ),
    "sale.complete": ANY_PRODUCER,
    "risk.report": ANY_PRODUCER,
    "risk.resolve": ANY_PRODUCER,
    "security.unblock": STAFF_ROLES,
})
assert "producers.verify" in OPERATIONS
assert "aid.approve" in OPERATIONS


# ---- additive RUN D: ops comerciales ----
OPERATIONS.update({
    "sale.publish": (
        PRODUCER, GOVERNMENT, ADMINISTRATOR,
    ),
    "sale.offer": (
        PRODUCER, COMPANY, GOVERNMENT,
        ADMINISTRATOR,
    ),
    "sale.accept": (
        PRODUCER, GOVERNMENT, ADMINISTRATOR,
    ),
    "sale.pay": (
        PRODUCER, COMPANY, GOVERNMENT,
        ADMINISTRATOR,
    ),
    "sale.deliver": (
        PRODUCER, GOVERNMENT, ADMINISTRATOR,
    ),
    "inventory.add": (
        PRODUCER, GOVERNMENT, ADMINISTRATOR,
    ),
    "export.create": (
        PRODUCER, COMPANY, GOVERNMENT,
        ADMINISTRATOR,
    ),
    "shipment.create": (
        PRODUCER, COMPANY, GOVERNMENT,
        ADMINISTRATOR,
    ),
    "shipment.update": (
        PRODUCER, COMPANY, GOVERNMENT,
        ADMINISTRATOR,
    ),
    "market.price.add": (
        PRODUCER, COMPANY, GOVERNMENT,
        OPERATOR, ADMINISTRATOR,
    ),
})


# ---- additive RUN E: ops recursos y riesgo ----
OPERATIONS.update({
    "equipment.create": (
        PRODUCER, GOVERNMENT, ADMINISTRATOR,
    ),
    "infrastructure.create": (
        PRODUCER, GOVERNMENT, ADMINISTRATOR,
    ),
    "asset.log": (
        PRODUCER, GOVERNMENT, ADMINISTRATOR,
    ),
    "asset.value": (
        PRODUCER, GOVERNMENT, ADMINISTRATOR,
    ),
    "risk.climate.evaluate": (
        PRODUCER, GOVERNMENT, OPERATOR,
        ADMINISTRATOR,
    ),
    "risk.productive.evaluate": (
        PRODUCER, GOVERNMENT, ADMINISTRATOR,
    ),
    "risk.impact.calculate": (
        PRODUCER, GOVERNMENT, ADMINISTRATOR,
    ),
    "risk.recovery": (
        PRODUCER, GOVERNMENT, ADMINISTRATOR,
    ),
    "alert.resolve": STAFF_ROLES,
    "response.create": (
        PRODUCER, GOVERNMENT, ADMINISTRATOR,
    ),
    "response.update": (
        PRODUCER, GOVERNMENT, ADMINISTRATOR,
    ),
})


# ---- additive RUN F: ops ecosistema ----
OPERATIONS.update({
    "network.emit": (
        PRODUCER, COMPANY, GOVERNMENT,
        OPERATOR, ADMINISTRATOR,
    ),
})

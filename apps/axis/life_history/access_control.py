"""AXIS granular access control."""
from __future__ import annotations

import unittest

from apps.axis.life_history.permissions import (
    HISTORY_READERS,
    REGISTRY_OPERATORS,
)

OPERATIONS = {
    "birth.register": REGISTRY_OPERATORS,
    "birth.amend": REGISTRY_OPERATORS,
    "health.record": ("medico",),
    "justice.case": ("abogado", "gobierno"),
    "justice.status": ("abogado", "gobierno"),
    "security.report": ("policia", "gobierno"),
    "security.advance": ("policia", "gobierno"),
    "clearance.emit": REGISTRY_OPERATORS,
    "history.read": HISTORY_READERS,
    "zid.upgrade": REGISTRY_OPERATORS
    + ("biometric-enroll",),
}


def authorize(operation, role):
    allowed = OPERATIONS.get(operation)
    if allowed is None:
        raise ValueError(
            "unknown operation: " + operation
        )
    return role in allowed


class AccessControlTests(unittest.TestCase):
    def test_roles_allowed(self):
        self.assertTrue(
            authorize(
                "birth.register",
                "registrador_civil",
            )
        )
        self.assertTrue(
            authorize(
                "health.record", "medico"
            )
        )
        self.assertTrue(
            authorize(
                "clearance.emit", "gobierno"
            )
        )

    def test_roles_denied(self):
        self.assertFalse(
            authorize(
                "clearance.emit", "paciente"
            )
        )
        self.assertFalse(
            authorize(
                "security.report", "medico"
            )
        )

    def test_unknown_operation(self):
        with self.assertRaises(ValueError):
            authorize("hack.admin", "gobierno")


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Longitudinal screen E2E over real HTTP."""
from __future__ import annotations

import threading
import unittest
from urllib.request import urlopen

from apps.axis.infrastructure.persistence.axis_store import (
    AxisStore,
)
from apps.axis.life_history.health_service import (
    HealthLifeLink,
)
from apps.axis.life_history.service import (
    LifeHistoryService,
)
from apps.axis.life_history.store import (
    LifeHistoryStore,
)
from apps.axis.server import serve_axis
from shared_engines.storage.database import (
    SQLiteAdapter,
)

_MOTHER = "ZID-mother-e2e"


class _FakeNetwork:
    def get(self, path):
        zid = path.rsplit("/", 1)[-1]
        if zid == _MOTHER:
            return (
                True,
                {"status": "ACTIVE"},
                None,
            )
        return (
            False,
            None,
            "unknown identity",
        )

    def post(self, path, payload):
        if path == "/documents/seal":
            return (
                True,
                {"document_id": "DOC-e2e"},
                None,
            )
        if path == "/history/append":
            return (
                True,
                {"appended": True},
                None,
            )
        return (False, None, "unknown")


class LongitudinalScreenE2E(unittest.TestCase):
    def test_screen_shows_chained_life(self) -> None:
        from shared_engines.common.clocks import (
            SystemClock,
        )

        db = SQLiteAdapter(":memory:")
        clock = SystemClock()
        life = LifeHistoryService(
            store=LifeHistoryStore(db, clock),
            client=_FakeNetwork(),
        )
        birth = (
            life.register_birth_with_network(
                registrar_account=(
                    "AX-reg-1"
                ),
                child_name="Bebe Pantalla",
                birth_date="2025-01-15",
                birth_place="San Salvador",
                sex="F",
                mother_name="Maria",
                mother_zid=_MOTHER,
            )
        )
        person_id = str(birth["person_id"])
        life.attach_zid_with_audit(
            person_id,
            zid="ZID-newborn-screen",
            actor="biometric-enroll",
        )
        store = AxisStore(db, clock)
        store.add_account(
            account_id="AX-pat-scr",
            zid="ZID-newborn-screen",
            name="Bebe Pantalla",
            role="paciente",
        )
        store.add_account(
            account_id="AX-doc-scr",
            zid=None,
            name="Dr Screen",
            role="medico",
        )
        server = serve_axis(
            store,
            _FakeNetwork(),
            life_history_service=life,
        )
        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
        )
        thread.start()
        base = (
            "http://127.0.0.1:"
            f"{server.bound_port}"
        )
        try:
            link = HealthLifeLink(
                store=store, life=life
            )
            self.assertTrue(
                link.record_exam(
                    exam_id="EXM-scr",
                    patient_account=(
                        "AX-pat-scr"
                    ),
                    doctor_account=(
                        "AX-doc-scr"
                    ),
                    exam_type="sangre",
                )
            )
            with urlopen(
                base
                + "/axis/longitudinal/"
                "AX-pat-scr",
                timeout=10,
            ) as response:
                html = (
                    response.read().decode(
                        "utf-8"
                    )
                )
            self.assertIn(
                "Historial Longitudinal",
                html,
            )
            self.assertIn(
                "Bebe Pantalla", html
            )
            self.assertIn(
                "birth_registered", html
            )
            self.assertIn(
                "health_exam", html
            )
            self.assertIn(
                "VERIFICADA", html
            )
            with urlopen(
                base
                + "/axis/paciente/"
                "AX-pat-scr",
                timeout=10,
            ) as response:
                patient_html = (
                    response.read().decode(
                        "utf-8"
                    )
                )
            self.assertIn(
                "/axis/longitudinal/"
                "AX-pat-scr",
                patient_html,
            )
            store.add_account(
                account_id="AX-ext-scr",
                zid=None,
                name="Externo",
                role="paciente",
            )
            with urlopen(
                base
                + "/axis/longitudinal/"
                "AX-ext-scr",
                timeout=10,
            ) as response:
                ext_html = (
                    response.read().decode(
                        "utf-8"
                    )
                )
            self.assertIn(
                "no esta vinculada",
                ext_html,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)

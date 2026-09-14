"""Ops server E2E over real HTTP."""
from __future__ import annotations

import threading
import unittest
from urllib.request import (
    Request,
    urlopen,
)

from apps.axis.infrastructure.persistence.axis_store import (
    AxisStore,
)
from apps.axis.life_history.ops_server import (
    serve_ops,
)
from apps.axis.life_history.service import (
    LifeHistoryService,
)
from apps.axis.life_history.store import (
    LifeHistoryStore,
)

_SUBJECT = "ZID-subject-ops"
_MOTHER = "ZID-mother-ops"


class _FakeNetwork:
    def get(self, path):
        zid = path.rsplit("/", 1)[-1]
        if zid in (_SUBJECT, _MOTHER):
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
                {"document_id": "DOC-o"},
                None,
            )
        if path == "/history/append":
            return (
                True,
                {"appended": True},
                None,
            )
        return (False, None, "unknown")


class OpsServerE2E(unittest.TestCase):
    def test_justice_and_security(self) -> None:
        from shared_engines.common.clocks import (
            SystemClock,
        )
        from shared_engines.storage.database import (
            SQLiteAdapter,
        )

        db = SQLiteAdapter(":memory:")
        clock = SystemClock()
        life = LifeHistoryService(
            store=LifeHistoryStore(
                db, clock
            ),
            client=_FakeNetwork(),
        )
        birth = (
            life.register_birth_with_network(
                registrar_account=(
                    "AX-reg-1"
                ),
                child_name="Sujeto Ops",
                birth_date="1990-06-01",
                birth_place="San Salvador",
                sex="M",
                mother_name="Madre Ops",
                mother_zid=_MOTHER,
            )
        )
        person_id = str(
            birth["person_id"]
        )
        life.attach_zid_with_audit(
            person_id,
            zid=_SUBJECT,
            actor="biometric-enroll",
        )
        store = AxisStore(db, clock)
        store.add_account(
            account_id="AX-cli-o",
            zid=_SUBJECT,
            name="Sujeto Ops",
            role="paciente",
        )
        store.add_account(
            account_id="AX-law-o",
            zid=None,
            name="Abogado O",
            role="abogado",
        )
        store.add_account(
            account_id="AX-pol-o",
            zid=None,
            name="Agente O",
            role="policia",
        )
        server = serve_ops(
            store, life
        )
        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
        )
        thread.start()
        base = (
            "http://127.0.0.1:"
            + str(server.bound_port)
        )

        def pf(path, doc):
            req = Request(
                base + path,
                data=(
                    "&".join(
                        str(k)
                        + "="
                        + str(v)
                        for k, v in doc.items()
                    )
                ).encode("utf-8"),
                method="POST",
            )
            with urlopen(
                req, timeout=10
            ) as r:
                return r.read().decode(
                    "utf-8"
                )

        def h(path):
            with urlopen(
                base + path,
                timeout=10,
            ) as r:
                return r.read().decode(
                    "utf-8"
                )

        try:
            self.assertIn(
                "JUSTICIA",
                h("/ops/justicia"),
            )
            self.assertIn(
                "SEGURIDAD",
                h("/ops/seguridad"),
            )
            case_html = pf(
                "/ops/justicia",
                {
                    "client_account": "AX-cli-o",
                    "lawyer_account": "AX-law-o",
                    "detail": "robo",
                },
            )
            self.assertIn(
                "Caso", case_html
            )
            types = [
                e["event_type"]
                for e in life._store.events_of(
                    person_id
                )
            ]
            self.assertIn(
                "justice_case", types
            )
            inc_html = pf(
                "/ops/seguridad",
                {
                    "police_account": "AX-pol-o",
                    "subject_account": "AX-cli-o",
                    "description": "robo",
                },
            )
            self.assertIn(
                "Incidente", inc_html
            )
            types = [
                e["event_type"]
                for e in life._store.events_of(
                    person_id
                )
            ]
            self.assertIn(
                "security_incident",
                types,
            )
            self.assertTrue(
                life._store.events_verify(
                    person_id
                )
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)

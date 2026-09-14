"""Clearance screen E2E."""
from __future__ import annotations

import threading
import unittest

from urllib.error import HTTPError
from urllib.request import (
    Request,
    urlopen,
)

from apps.axis.life_history.clearance_ops import (
    serve_clearance,
)
from apps.axis.life_history.clearance_service import (
    ClearanceEmitter,
)
from apps.axis.life_history.service import (
    LifeHistoryService,
)
from apps.axis.life_history.store import (
    LifeHistoryStore,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)


class _FakeNet:
    def get(self, path):
        return True, {"status": "ACTIVE"}, None

    def post(self, path, payload):
        if path == "/documents/seal":
            return (
                True,
                {"document_id": "DOC-c"},
                None,
            )
        if path == "/history/append":
            return (
                True,
                {"appended": True},
                None,
            )
        return False, None, "unknown"


class _Clock:
    def now(self):
        import time

        return time.time()


class ClearanceOpsE2E(unittest.TestCase):
    def test_emit_and_denied(self):
        db = SQLiteAdapter(":memory:")
        net_db = SQLiteAdapter(":memory:")
        life = LifeHistoryService(
            store=LifeHistoryStore(
                db, _Clock()
            ),
            client=_FakeNet(),
        )
        emitter = ClearanceEmitter(
            store=db,
            life=life,
            client=_FakeNet(),
            network_db=net_db,
            master_key_hex="ab" * 32,
        )
        server = serve_clearance(emitter)
        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
        )
        thread.start()
        base = (
            "http://127.0.0.1:"
            + str(server.bound_port)
        )

        def post(path, doc):
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
            try:
                with urlopen(
                    req, timeout=10
                ) as r:
                    return r.read().decode(
                        "utf-8"
                    )
            except HTTPError as exc:
                return exc.read().decode(
                    "utf-8", "replace"
                )

        try:
            ok_page = post(
                "/clr/emision",
                {
                    "operator_account": "AX-gob",
                    "operator_role": "gobierno",
                    "subject_zid": "ZID-suj-1",
                },
            )
            self.assertIn(
                "Certificacion emitida",
                ok_page,
            )
            self.assertIn(
                "SIN_REGISTROS_REPORTADOS",
                ok_page,
            )
            denied = post(
                "/clr/emision",
                {
                    "operator_account": "AX-any",
                    "operator_role": "paciente",
                    "subject_zid": "ZID-suj-2",
                },
            )
            self.assertIn(
                "Rechazada", denied
            )
            rows = net_db.query_all(
                "SELECT * FROM"
                " clearance_requests"
            )
            self.assertEqual(1, len(rows))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            db.close()
            net_db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)

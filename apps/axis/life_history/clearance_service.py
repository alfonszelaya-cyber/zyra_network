"""AXIS clearance emitter - additive module.

The operator (gobierno/policia role) requests a
background certification for a subject ZID. The
Network engine (shared_engines.security.clearance)
does the authority scan and signs. AXIS emits the
sealed document and audits the emission.

Only REGISTRY_OPERATORS may emit. Every emission
is recorded in the life history chain of the
subject (existence only: 'certification issued').
"""
from __future__ import annotations

import base64
import json
import unittest

from apps.axis.life_history.permissions import (
    REGISTRY_OPERATORS,
)
from apps.axis.life_history.service import (
    LifeHistoryService,
)
from apps.axis.life_history.store import (
    LifeHistoryStore,
)

EMITTED = "certification_issued"


class ClearanceNotAuthorizedError(Exception):
    """Requester is not a registry operator."""


class ClearanceEmitter:
    def __init__(
        self,
        *,
        store,
        life: LifeHistoryService,
        client,
        network_db,
        master_key_hex: str,
    ) -> None:
        self._store = store
        self._life = life
        self._client = client
        from shared_engines.security.clearance import (
            ClearanceEngine,
        )

        self._engine = ClearanceEngine(
            db=network_db,
            clock=life._store._clock,
            master_key_hex=master_key_hex,
        )

    def emit(
        self,
        *,
        operator_account: str,
        operator_role: str,
        subject_zid: str,
    ) -> dict:
        if operator_role not in (
            REGISTRY_OPERATORS
        ):
            raise (
                ClearanceNotAuthorizedError(
                    "operator not authorized:"
                    f" {operator_role}"
                )
            )
        cert = self._engine.certify(
            requester=operator_account,
            subject_zid=subject_zid,
            life_store=self._life._store,
        )
        payload_b64 = base64.b64encode(
            json.dumps(
                {
                    k: cert[k]
                    for k in (
                        "cert_id",
                        "finding",
                        "issued_at",
                        "signature",
                    )
                }
            ).encode("utf-8")
        ).decode("ascii")
        sealed = self._client.post(
            "/documents/seal",
            {
                "owner_zid": subject_zid,
                "title": (
                    "Certificacion "
                    + cert["cert_id"]
                ),
                "content_b64": payload_b64,
                "actor_app": "axis",
            },
        )
        document_id = None
        if sealed[0] and sealed[1]:
            for key in (
                "document_id",
                "seal_id",
            ):
                value = (sealed[1] or {}).get(key)
                if isinstance(value, str):
                    document_id = value
                    break
        for person_row in self._life._store._db.query_all(
            "SELECT person_id FROM life_persons"
            " WHERE zid = ?",
            (subject_zid,),
        ):
            try:
                self._life._store.add_life_event(
                    str(
                        person_row["person_id"]
                    ),
                    actor=operator_account,
                    event_type=EMITTED,
                    detail=cert["cert_id"],
                )
            except Exception:
                pass
        return {
            **cert,
            "document_id": document_id,
        }


class EmitterTests(unittest.TestCase):
    def _boot(self, role="gobierno"):
        from shared_engines.common.clocks import (
            SystemClock,
        )
        from shared_engines.storage.database import (
            SQLiteAdapter,
        )

        db = SQLiteAdapter(":memory:")
        clock = SystemClock()
        net_db = SQLiteAdapter(":memory:")
        life = LifeHistoryService(
            store=LifeHistoryStore(db, clock),
            client=_FakeNet(),
        )
        emitter = ClearanceEmitter(
            store=db,
            life=life,
            client=_FakeNet(),
            network_db=net_db,
            master_key_hex="ab" * 32,
        )
        return life, emitter, role

    def test_operator_emits(self) -> None:
        life, emitter, _role = self._boot()
        cert = emitter.emit(
            operator_account="AX-gob-1",
            operator_role="gobierno",
            subject_zid="ZID-any-1",
        )
        self.assertEqual(
            "SIN_REGISTROS_REPORTADOS",
            cert["finding"],
        )
        self.assertTrue(cert["document_id"])

    def test_non_operator_rejected(self) -> None:
        life, emitter, _role = self._boot(
            role="paciente"
        )
        try:
            emitter.emit(
                operator_account="AX-any",
                operator_role="paciente",
                subject_zid="ZID-any-2",
            )
        except Exception:
            pass
        else:
            self.fail("paciente emitted")

    def test_emission_chained_to_life(self) -> None:
        from apps.axis.infrastructure.persistence.axis_store import (
            AxisStore,
        )

        life, emitter, _role = self._boot()
        birth = life.register_birth_with_network(
            registrar_account="AX-reg-1",
            child_name="Sujeto Cert",
            birth_date="1990-01-01",
            birth_place="SS",
            sex="M",
            mother_name="M",
            mother_zid="ZID-mother-c1",
        )
        person_id = str(birth["person_id"])
        life.attach_zid_with_audit(
            person_id,
            zid="ZID-cert-1",
            actor="enroll",
        )
        cert = emitter.emit(
            operator_account="AX-gob-1",
            operator_role="gobierno",
            subject_zid="ZID-cert-1",
        )
        events = life._store.events_of(person_id)
        self.assertEqual(
            EMITTED, events[-1]["event_type"]
        )
        self.assertTrue(
            life._store.events_verify(person_id)
        )


class _FakeNet:
    def get(self, path):
        return True, {"status": "ACTIVE"}, None

    def post(self, path, payload):
        if path == "/documents/seal":
            return (
                True,
                {"document_id": "DOC-clr"},
                None,
            )
        if path == "/history/append":
            return (
                True,
                {"appended": True},
                None,
            )
        return False, None, "unknown"


if __name__ == "__main__":
    unittest.main(verbosity=2)

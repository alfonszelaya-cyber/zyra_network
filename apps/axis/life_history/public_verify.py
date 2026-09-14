"""AXIS public verification - internal service.

One-time codes: authorized operator generates a
code for a subject ZID; the third party redeems
it through their app's own entry and receives a
Network-signed certification. Audited, single-use,
expiring. No HTTP surface - exposure belongs to
each app's entry.
"""
import unittest
import uuid

from apps.axis.life_history.access_control import (
    authorize,
)
from apps.axis.life_history.service import (
    LifeHistoryService,
)
from apps.axis.life_history.store import (
    LifeHistoryStore,
)
from shared_engines.security.clearance import (
    ClearanceEngine,
)


class CodeNotFoundError(Exception):
    pass


class CodeAlreadyUsedError(Exception):
    pass


class CodeExpiredError(Exception):
    pass


class NotAuthorizedError(Exception):
    pass


class PublicVerifyService:
    def __init__(
        self,
        *,
        life,
        network_db,
        master_key_hex,
        clock=None,
        code_ttl_seconds=3600.0,
    ):
        self._life = life
        self._clock = (
            clock
            if clock is not None
            else life._store._clock
        )
        self._ttl = code_ttl_seconds
        self._engine = ClearanceEngine(
            db=network_db,
            clock=self._clock,
            master_key_hex=master_key_hex,
        )
        self._life._store._db.execute(
            "CREATE TABLE IF NOT EXISTS"
            " public_access_codes ("
            " code TEXT PRIMARY KEY,"
            " subject_zid TEXT NOT NULL,"
            " created_by TEXT NOT NULL,"
            " created_at REAL NOT NULL,"
            " redeemed INTEGER NOT NULL,"
            " redeemed_by TEXT,"
            " redeemed_at REAL)"
        )

    def generate_code(
        self,
        *,
        subject_zid,
        operator_account,
        operator_role,
    ):
        if not authorize(
            "code.generate", operator_role
        ):
            raise NotAuthorizedError(
                "role not authorized: "
                + operator_role
            )
        if not subject_zid.startswith("ZID-"):
            raise ValueError(
                "subject must be a ZID"
            )
        code = (
            "VRF-"
            + uuid.uuid4().hex[:12]
        )
        now = self._clock.now()
        self._life._store._db.execute(
            "INSERT INTO public_access_codes ("
            " code, subject_zid, created_by,"
            " created_at, redeemed,"
            " redeemed_by, redeemed_at)"
            " VALUES (?,?,?,?,0,NULL,NULL)",
            (
                code,
                subject_zid,
                operator_account,
                now,
            ),
        )
        return {
            "code": code,
            "subject_zid": subject_zid,
            "expires_in_seconds": self._ttl,
        }

    def redeem_code(
        self,
        *,
        code,
        requester,
        requester_role,
    ):
        if not authorize(
            "code.redeem", requester_role
        ):
            raise NotAuthorizedError(
                "role not authorized: "
                + requester_role
            )
        if not requester.strip():
            raise ValueError(
                "requester required"
            )
        row = self._life._store._db.query_one(
            "SELECT * FROM"
            " public_access_codes WHERE"
            " code = ?",
            (code,),
        )
        if row is None:
            raise CodeNotFoundError(
                "unknown code"
            )
        if int(row["redeemed"]) == 1:
            raise CodeAlreadyUsedError(
                "code already used"
            )
        now = self._clock.now()
        age = now - float(row["created_at"])
        if age > self._ttl:
            raise CodeExpiredError(
                "code expired"
            )
        cert = self._engine.certify(
            requester=requester,
            subject_zid=str(
                row["subject_zid"]
            ),
            life_store=self._life._store,
        )
        self._life._store._db.execute(
            "UPDATE public_access_codes SET"
            " redeemed = 1, redeemed_by = ?,"
            " redeemed_at = ? WHERE code = ?",
            (requester, now, code),
        )
        return {
            **cert,
            "redeemed_by": requester,
        }

    def verify_signature(self, *, cert):
        return self._engine.verify(cert=cert)


class _FakeNet:
    def get(self, path):
        return True, {"status": "ACTIVE"}, None

    def post(self, path, payload):
        if path == "/documents/seal":
            return (
                True,
                {"document_id": "DOC-pv"},
                None,
            )
        if path == "/history/append":
            return (
                True,
                {"appended": True},
                None,
            )
        return False, None, "unknown"


class _MutableClock:
    def __init__(self):
        self._t = 1000000.0

    def now(self):
        return self._t

    def advance(self, seconds):
        self._t += seconds


class PublicVerifyTests(unittest.TestCase):
    def _boot(self, ttl=3600.0):
        from shared_engines.storage.database import (
            SQLiteAdapter,
        )

        db = SQLiteAdapter(":memory:")
        net_db = SQLiteAdapter(":memory:")
        clock = _MutableClock()
        life = LifeHistoryService(
            store=LifeHistoryStore(db, clock),
            client=_FakeNet(),
        )
        life.register_birth_with_network(
            registrar_account="AX-reg-1",
            child_name="Candidato",
            birth_date="1995-01-01",
            birth_place="SS",
            sex="M",
            mother_name="Madre",
            mother_zid="ZID-mother-pv",
        )
        person = life._store._db.query_one(
            "SELECT person_id FROM life_persons"
        )
        life.attach_zid_with_audit(
            str(person["person_id"]),
            zid="ZID-candidate-1",
            actor="enroll",
        )
        svc = PublicVerifyService(
            life=life,
            network_db=net_db,
            master_key_hex="ab" * 32,
            clock=clock,
            code_ttl_seconds=ttl,
        )
        return svc, clock

    def test_generate_and_redeem(self) -> None:
        svc, _clock = self._boot()
        code = svc.generate_code(
            subject_zid="ZID-candidate-1",
            operator_account="AX-gob",
            operator_role="gobierno",
        )
        self.assertTrue(
            code["code"].startswith("VRF-")
        )
        cert = svc.redeem_code(
            code=code["code"],
            requester="Empleador-X",
            requester_role="empleador",
        )
        self.assertEqual(
            "SIN_REGISTROS_REPORTADOS",
            cert["finding"],
        )
        self.assertTrue(
            svc.verify_signature(cert=cert)
        )

    def test_single_use_only(self) -> None:
        svc, _clock = self._boot()
        code = svc.generate_code(
            subject_zid="ZID-candidate-1",
            operator_account="AX-gob",
            operator_role="gobierno",
        )
        svc.redeem_code(
            code=code["code"],
            requester="Emp-1",
            requester_role="empleador",
        )
        with self.assertRaises(
            CodeAlreadyUsedError
        ):
            svc.redeem_code(
                code=code["code"],
                requester="Emp-2",
                requester_role="empleador",
            )

    def test_expired_code_rejected(self) -> None:
        svc, clock = self._boot(ttl=10.0)
        code = svc.generate_code(
            subject_zid="ZID-candidate-1",
            operator_account="AX-gob",
            operator_role="gobierno",
        )
        clock.advance(20.0)
        with self.assertRaises(
            CodeExpiredError
        ):
            svc.redeem_code(
                code=code["code"],
                requester="Emp",
                requester_role="empleador",
            )

    def test_tampered_cert_rejected(
        self,
    ) -> None:
        svc, _clock = self._boot()
        code = svc.generate_code(
            subject_zid="ZID-candidate-1",
            operator_account="AX-gob",
            operator_role="gobierno",
        )
        cert = svc.redeem_code(
            code=code["code"],
            requester="Emp",
            requester_role="empleador",
        )
        tampered = dict(cert)
        tampered["finding"] = (
            "CON_REGISTROS_REPORTADOS"
        )
        self.assertFalse(
            svc.verify_signature(
                cert=tampered
            )
        )

    def test_generate_needs_authority(
        self,
    ) -> None:
        svc, _clock = self._boot()
        with self.assertRaises(
            NotAuthorizedError
        ):
            svc.generate_code(
                subject_zid=(
                    "ZID-candidate-1"
                ),
                operator_account="AX-any",
                operator_role="paciente",
            )

    def test_redeem_needs_authority(
        self,
    ) -> None:
        svc, _clock = self._boot()
        code = svc.generate_code(
            subject_zid="ZID-candidate-1",
            operator_account="AX-gob",
            operator_role="gobierno",
        )
        with self.assertRaises(
            NotAuthorizedError
        ):
            svc.redeem_code(
                code=code["code"],
                requester="Alguien",
                requester_role="hacker",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)

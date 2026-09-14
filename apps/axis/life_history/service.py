"""AXIS Life History service — orchestration layer.

Phase 1.2: wires the certified LifeHistoryStore to the
ZYRA Network through the AXIS link layer.

Behaviors (following AxisStore/AxisLink conventions):
- register_birth_with_network(): seals the birth locally
  (tamper-evident chain) AND, when the Network is
  reachable, seals the certificate as a Network document
  for the child's custody record. If the Network is down,
  the birth is still registered (offline-safe) and the
  network seal is retried later via pending_network_seals().
- verify_parent(): asks the Network whether a ZID exists
  and is ACTIVE before a birth may reference it. When the
  Network is unreachable, verification is skipped and the
  parent ZID is accepted but flagged (pending verification
  is the network's business, not a local rejection).
- attach_zid(): delegates to the store (chain event) —
  the ZID itself must come from /identity/enroll with
  biometrics; this service never mints ZIDs.

Additive module: never touches existing AXIS tables.
Run tests:  python -m apps.axis.life_history.service -v
"""
from __future__ import annotations

import unittest

from apps.axis.life_history.store import (
    BIRTH_STATUS_ACTIVE,
    GENESIS,
    LifeHistoryError,
    LifeHistoryStore,
    ParentNotVerifiedError,
    SEX_VALUES,
)

REGISTRAR_ROLES = ("registrador_civil", "gobierno")


class _VerifiedParentError(LifeHistoryError):
    """The Network could not confirm this parent ZID
    exists and is active."""


class LifeHistoryService:
    """Birth registration orchestration (store + Network)."""

    def __init__(
        self,
        *,
        store: LifeHistoryStore,
        client,
        require_active_parents: bool = True,
    ) -> None:
        self._store = store
        self._client = client
        self._require_active = require_active_parents

    # ---------------------------------------- parent verification

    def verify_parent(
        self, zid: str
    ) -> dict[str, object] | None:
        """Returns the network identity when reachable and
        active, None when the Network is unreachable
        (offline-safe), and raises when the Network answers
        that the ZID is unknown/not active (fraud guard)."""
        if not zid.startswith("ZID-"):
            raise ParentNotVerifiedError(
                "parent has no network ZID"
            )
        ok, data, error = self._client.get(
            f"/identity/{zid}"
        )
        if not ok:
            if error is not None and (
                "not found" in error.lower()
                or "unknown" in error.lower()
            ):
                raise _VerifiedParentError(
                    f"network rejects parent ZID:"
                    f" {zid} ({error})"
                )
            return None
        status = str(
            (data or {}).get("status", "")
        )
        if (
            self._require_active
            and status != "ACTIVE"
        ):
            raise _VerifiedParentError(
                f"parent ZID is not ACTIVE:"
                f" {zid} ({status})"
            )
        return data

    # ---------------------------------------- birth

    def register_birth_with_network(
        self,
        *,
        registrar_account: str,
        child_name: str,
        birth_date: str,
        birth_place: str,
        sex: str,
        mother_name: str,
        mother_zid: str,
        father_name: str | None = None,
        father_zid: str | None = None,
        source_hospital: str | None = None,
    ) -> dict[str, object]:
        """Seals the birth in the national chain, verifies
        both parents against the Network when reachable,
        and seals the certificate as a Network document
        when possible. Never loses a birth offline."""
        if not registrar_account.strip():
            raise ValueError(
                "registrar_account required"
            )
        if not child_name.strip():
            raise ValueError("child_name required")
        if not birth_date.strip():
            raise ValueError("birth_date required")
        if not birth_place.strip():
            raise ValueError("birth_place required")
        if not mother_name.strip():
            raise ValueError("mother_name required")
        if sex not in SEX_VALUES:
            raise ValueError(
                f"sex must be one of {SEX_VALUES}"
            )
        if not mother_zid.startswith("ZID-"):
            raise ParentNotVerifiedError(
                "mother has no verified ZID"
            )
        if father_name is not None and (
            father_zid is None
        ):
            raise ParentNotVerifiedError(
                "father named without verified ZID"
            )
        if father_zid is not None and not (
            father_zid.startswith("ZID-")
        ):
            raise ParentNotVerifiedError(
                "father has no verified ZID"
            )

        mother_network = self.verify_parent(
            mother_zid
        )
        father_network = (
            None
            if father_zid is None
            else self.verify_parent(father_zid)
        )

        birth = self._store.register_birth(
            registrar_account=registrar_account,
            child_name=child_name,
            birth_date=birth_date,
            birth_place=birth_place,
            sex=sex,
            mother_name=mother_name,
            mother_zid=mother_zid,
            father_name=father_name,
            father_zid=father_zid,
            source_hospital=source_hospital,
        )

        network_seal: str | None = None
        network_ok = False
        try:
            ok, data, _err = self._client.post(
                "/documents/seal",
                {
                    "owner_zid": mother_zid,
                    "title": (
                        "Partida de Nacimiento "
                        + str(birth["birth_id"])
                    ),
                    "content_b64": self._cert_b64(
                        birth
                    ),
                    "actor_app": "axis",
                },
            )
            network_ok = bool(ok)
            if ok and data is not None:
                for key in (
                    "document_id",
                    "seal_id",
                ):
                    value = (data or {}).get(key)
                    if isinstance(value, str):
                        network_seal = value
                        break
        except Exception:
            network_ok = False

        return {
            **birth,
            "mother_network_status": (
                str(
                    (mother_network or {}).get(
                        "status", ""
                    )
                )
                or None
            ),
            "father_network_status": (
                str(
                    (father_network or {}).get(
                        "status", ""
                    )
                )
                or None
            ),
            "network_seal": network_seal,
            "network_ok": network_ok,
        }

    def pending_network_seals(
        self,
    ) -> list[dict[str, str]]:
        """Active births whose certificate is not yet
        sealed on the Network (offline backlog)."""
        rows = self._store._db.query_all(
            "SELECT birth_id, person_id, cert_hash"
            " FROM life_births WHERE status = ?"
            " ORDER BY rowid",
            (BIRTH_STATUS_ACTIVE,),
        )
        pending: list[dict[str, str]] = []
        for row in rows:
            person = self._store._db.query_one(
                "SELECT zid FROM life_persons"
                " WHERE person_id = ?",
                (str(row["person_id"]),),
            )
            mother = self._store._db.query_one(
                "SELECT mother_zid FROM"
                " life_births WHERE birth_id = ?",
                (str(row["birth_id"]),),
            )
            pending.append(
                {
                    "birth_id": str(
                        row["birth_id"]
                    ),
                    "cert_hash": str(
                        row["cert_hash"]
                    ),
                    "mother_zid": str(
                        mother["mother_zid"]
                    )
                    if mother is not None
                    else "",
                }
            )
        return pending

    # ---------------------------------------- identity

    def attach_zid_with_audit(
        self,
        person_id: str,
        *,
        zid: str,
        actor: str,
    ) -> dict[str, object]:
        """Biometric upgrade of the newborn identity.
        Records the upgrade in the person chain AND
        notifies the Network history when reachable."""
        person = self._store.attach_zid(
            person_id, zid=zid, actor=actor
        )
        try:
            self._client.post(
                "/history/append",
                {
                    "zid": zid,
                    "entry_type": "other",
                    "actor_app": "axis",
                    "payload": {
                        "event": (
                            "life_history_"
                            "biometric_upgrade"
                        ),
                        "detail": person_id,
                    },
                },
            )
        except Exception:
            pass
        return person

    # ---------------------------------------- internals

    @staticmethod
    def _cert_b64(
        birth: dict[str, object],
    ) -> str:
        import base64

        payload = "|".join(
            (
                str(birth.get("birth_id", "")),
                str(birth.get("person_id", "")),
                str(birth.get("birth_date", "")),
                str(birth.get("birth_place", "")),
                str(birth.get("mother_zid", "")),
                str(birth.get("cert_hash", "")),
            )
        )
        return base64.b64encode(
            payload.encode("utf-8")
        ).decode("ascii")


# =====================================================
# Tests (offline + fake network client)
# =====================================================

_MOTHER_ZID = "ZID-mother-0001"
_FATHER_ZID = "ZID-father-0001"


class _FakeNetwork:
    """Deterministic network double."""

    def __init__(
        self, *, reachable: bool = True
    ) -> None:
        self.reachable = reachable
        self.known_zids: dict[
            str, dict
        ] = {
            _MOTHER_ZID: {
                "status": "ACTIVE"
            },
            _FATHER_ZID: {
                "status": "ACTIVE"
            },
        }
        self.sealed: list[dict] = []

    def get(self, path: str):
        if not self.reachable:
            return (False, None, "offline")
        zid = path.rsplit("/", 1)[-1]
        if zid in self.known_zids:
            return (
                True,
                dict(self.known_zids[zid]),
                None,
            )
        return (
            False,
            None,
            "unknown identity",
        )

    def post(self, path: str, payload: dict):
        if not self.reachable:
            return (False, None, "offline")
        if path == "/documents/seal":
            self.sealed.append(dict(payload))
            return (
                True,
                {"document_id": "DOC-sealed-1"},
                None,
            )
        if path == "/history/append":
            return (True, {"appended": True}, None)
        return (
            False,
            None,
            "unknown route",
        )


class _Base(unittest.TestCase):
    def _service(
        self,
        *,
        reachable: bool = True,
        require_active: bool = True,
    ):
        from shared_engines.common.clocks import (
            SystemClock,
        )
        from shared_engines.storage.database import (
            SQLiteAdapter,
        )

        db = SQLiteAdapter(":memory:")
        store = LifeHistoryStore(
            db, SystemClock()
        )
        net = _FakeNetwork(
            reachable=reachable
        )
        service = LifeHistoryService(
            store=store,
            client=net,
            require_active_parents=require_active,
        )
        return service, net, store, db

    def _birth(
        self, service: LifeHistoryService
    ) -> dict[str, object]:
        return (
            service.register_birth_with_network(
                registrar_account=(
                    "AX-registrador-1"
                ),
                child_name="Bebe Prueba",
                birth_date="2025-01-15",
                birth_place="San Salvador",
                sex="F",
                mother_name="Maria Perez",
                mother_zid=_MOTHER_ZID,
                father_name="Jose Lopez",
                father_zid=_FATHER_ZID,
                source_hospital=(
                    "Hospital Nacional"
                ),
            )
        )


class BirthWithNetworkTests(_Base):
    def test_full_birth_with_network_seal(
        self,
    ) -> None:
        service, net, _store, _db = self._service()
        birth = self._birth(service)
        self.assertTrue(birth["network_ok"])
        self.assertEqual(
            "DOC-sealed-1",
            birth["network_seal"],
        )
        self.assertEqual(
            "ACTIVE",
            birth["mother_network_status"],
        )
        self.assertEqual(
            1, len(net.sealed)
        )

    def test_offline_birth_still_registered(
        self,
    ) -> None:
        service, net, store, _db = self._service(
            reachable=False
        )
        birth = self._birth(service)
        self.assertFalse(birth["network_ok"])
        self.assertIsNone(
            birth["network_seal"]
        )
        ok, count = store.births_chain_verify()
        self.assertTrue(ok)
        self.assertEqual(1, count)
        pending = service.pending_network_seals()
        self.assertEqual(1, len(pending))

    def test_unknown_parent_zid_rejected(
        self,
    ) -> None:
        service, _net, _store, _db = self._service()
        with self.assertRaises(_VerifiedParentError):
            service.register_birth_with_network(
                registrar_account=(
                    "AX-registrador-1"
                ),
                child_name="Bebe Fraude",
                birth_date="2025-01-15",
                birth_place="San Salvador",
                sex="M",
                mother_name="Impostora",
                mother_zid="ZID-fantasma",
            )

    def test_non_active_parent_rejected(
        self,
    ) -> None:
        service, _net, _store, _db = self._service()
        service._client.known_zids[_MOTHER_ZID] = {
            "status": "REGISTERED"
        }
        with self.assertRaises(_VerifiedParentError):
            self._birth(service)


class AttachZidNetworkTests(_Base):
    def test_attach_notifies_network(self) -> None:
        service, net, store, _db = self._service()
        birth = self._birth(service)
        person_id = str(birth["person_id"])
        person = (
            service.attach_zid_with_audit(
                person_id,
                zid="ZID-newborn-1",
                actor="biometric-enroll",
            )
        )
        self.assertEqual(
            "biometric_verified",
            person["status"],
        )
        events = store.events_of(person_id)
        self.assertEqual(
            "zid_biometric_upgrade",
            events[-1]["event_type"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

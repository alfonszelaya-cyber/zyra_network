"""AXIS proofs: medical record with auto
appointment, legal case lifecycle, police
incident sealed evidence, role validation,
screens served."""
from __future__ import annotations

import threading
from pathlib import Path
from urllib.request import (
    Request,
    urlopen,
)

from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)

from apps.axis.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.axis.infrastructure.persistence.axis_store import (
    AxisStore,
)
from apps.axis.server import serve_axis


def _boot(tmp_path: Path):
    db = SQLiteAdapter(
        tmp_path / "axis.db"
    )
    clock = FrozenClock()
    store = AxisStore(db, clock)
    dead_client = NetworkClient(
        "http://127.0.0.1:1",
        timeout_seconds=1.0,
        max_retries=0,
    )
    server = serve_axis(store, dead_client)
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()
    base = (
        "http://127.0.0.1:"
        f"{server.bound_port}"
    )
    return db, store, base, server, thread


def test_medical_record_and_appointment(
    tmp_path: Path,
) -> None:
    db, store, base, server, thread = (
        _boot(tmp_path)
    )
    try:
        store.add_account(
            account_id="AX-doc1",
            zid=None,
            name="Dr. Ramirez",
            role="medico",
        )
        store.add_account(
            account_id="AX-pat1",
            zid=None,
            name="Maria Lopez",
            role="paciente",
        )
        row = store.add_medical_record(
            record_id="MED-001",
            patient_account="AX-pat1",
            doctor_account="AX-doc1",
            diagnosis="Gripe A",
            next_appointment=(
                "lunes 9am"
            ),
            sealed_doc="DOC-x1",
        )
        assert (
            row["next_appointment"]
            == "lunes 9am"
        )
        records = (
            store.medical_records_of(
                patient_account=(
                    "AX-pat1"
                )
            )
        )
        assert len(records) == 1
        assert records[0][
            "diagnosis"
        ] == "Gripe A"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


def test_legal_case_lifecycle(
    tmp_path: Path,
) -> None:
    db, store, base, server, thread = (
        _boot(tmp_path)
    )
    try:
        store.add_account(
            account_id="AX-law1",
            zid=None,
            name="Abogado Perez",
            role="abogado",
        )
        store.add_account(
            account_id="AX-cli1",
            zid=None,
            name="Cliente Uno",
            role="paciente",
        )
        case = store.add_legal_case(
            case_id="CASE-1",
            client_account="AX-cli1",
            lawyer_account="AX-law1",
            status="proceso",
            detail="audiencia pendiente",
            sealed_doc=None,
        )
        assert case["status"] == (
            "proceso"
        )
        updated = (
            store.update_case_status(
                case_id="CASE-1",
                status="libre",
                detail="liberado",
                sealed_doc=None,
            )
        )
        assert updated["status"] == (
            "libre"
        )
        cases = store.cases_for(
            lawyer_account="AX-law1"
        )
        assert len(cases) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


def test_incident_sealed_and_roles(
    tmp_path: Path,
) -> None:
    db, store, base, server, thread = (
        _boot(tmp_path)
    )
    try:
        store.add_account(
            account_id="AX-pol1",
            zid=None,
            name="Agente Cruz",
            role="policia",
        )
        store.add_incident(
            incident_id="INC-1",
            police_account="AX-pol1",
            description=(
                "robo reportado con"
                " evidencia"
            ),
            sealed_doc="DOC-ev1",
        )
        incidents = (
            store.list_incidents()
        )
        assert len(incidents) == 1
        assert incidents[0][
            "sealed_doc"
        ] == "DOC-ev1"
        try:
            store.add_account(
                account_id="AX-bad",
                zid=None,
                name="Fake",
                role="hacker",
            )
            raise AssertionError(
                "should fail"
            )
        except ValueError:
            pass
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


def test_screens_served(
    tmp_path: Path,
) -> None:
    db, store, base, server, thread = (
        _boot(tmp_path)
    )
    try:
        with urlopen(
            base + "/axis", timeout=10
        ) as response:
            home = response.read().decode(
                "utf-8"
            )
        assert "AXIS" in home
        assert "Registrarme" in home
        with urlopen(
            base
            + "/axis/gobierno",
            timeout=10,
        ) as response:
            gov = response.read().decode(
                "utf-8"
            )
        assert "Gobierno" in gov
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()

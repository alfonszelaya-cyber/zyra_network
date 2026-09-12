"""AXIS emergencias e2e ADD-ONLY - exam_id captured
from exam response, followup appointment verified via
store (pending reminders), emergency flow via HTTP,
timeline 4 (created + 2 dispatches + resolved),
original tests untouched."""
from __future__ import annotations

import json
import re
import socket
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

socket.setdefaulttimeout(20)

from shared_engines.common.clocks import FrozenClock
from shared_engines.runtime.capabilities import ZyraCapabilities
from shared_engines.runtime.combined_api import serve_combined
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.signatures import Ed25519Signer

from apps.axis.infrastructure.network.network_client import NetworkClient
from apps.axis.infrastructure.persistence.axis_store import AxisStore
from apps.axis.server import serve_axis


class _Eco:
    def __init__(self, tmp_path: Path) -> None:
        self.net_db = SQLiteAdapter(tmp_path / "network.db")
        signer, _ = Ed25519Signer.generate()
        self.kernel = ZyraKernel(
            db=self.net_db,
            clock=FrozenClock(),
            signer=signer,
            config=RuntimeConfig(host="127.0.0.1", port=0, api_token=None),
        )
        self.kernel.bootstrap_root()
        self.caps = ZyraCapabilities(
            self.net_db,
            FrozenClock(),
            identity=self.kernel.identity,
            signer=signer,
        )
        self.net_server = serve_combined(
            self.kernel, self.caps, host="127.0.0.1", port=0
        )
        threading.Thread(
            target=self.net_server.serve_forever, daemon=True
        ).start()
        self.net_base = (
            "http://127.0.0.1:"
            f"{self.net_server.server_address[1]}"
        )
        self.client = NetworkClient(self.net_base, max_retries=1)
        self.axis_db = SQLiteAdapter(tmp_path / "axis.db")
        self.store = AxisStore(self.axis_db, FrozenClock())
        self.axis_server = serve_axis(self.store, self.client)
        threading.Thread(
            target=self.axis_server.serve_forever, daemon=True
        ).start()
        self.axis_base = (
            "http://127.0.0.1:"
            f"{self.axis_server.bound_port}"
        )

    def close(self) -> None:
        self.axis_server.shutdown()
        self.axis_server.server_close()
        self.net_server.shutdown()
        self.net_server.server_close()
        self.axis_db.close()
        self.net_db.close()


def _pf(url: str, doc: dict) -> str:
    request = Request(
        url,
        data=(
            "&".join(str(k) + "=" + str(v) for k, v in doc.items())
        ).encode("utf-8"),
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as r:
            return r.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise AssertionError(
            "POST " + url + " -> HTTP " + str(exc.code)
            + " body: " + body[:400]
        )


def _pj(url: str, doc: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(doc).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as r:
            body = json.loads(r.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise AssertionError(
            "POST " + url + " -> HTTP " + str(exc.code)
            + " body: " + body[:400]
        )
    assert isinstance(body, dict)
    return body


def _h(url: str) -> str:
    with urlopen(url, timeout=15) as r:
        return r.read().decode("utf-8")


def _accounts(eco) -> tuple[str, str]:
    ok, data, _err = eco.client.post(
        "/identity/register",
        {
            "kind": "person",
            "display_name": "Dr Ramirez",
            "actor": "axis",
        },
    )
    assert ok is True and data is not None
    doctor_zid = str(data.get("zid"))
    assert doctor_zid.startswith("ZID-")
    eco.client.post(
        "/trust/complete", {"zid": doctor_zid, "actor": "axis"}
    )
    ok, data, _err = eco.client.post(
        "/identity/register",
        {
            "kind": "person",
            "display_name": "Maria Lopez",
            "actor": "axis",
        },
    )
    assert ok is True and data is not None
    patient_zid = str(data.get("zid"))
    eco.client.post(
        "/trust/complete", {"zid": patient_zid, "actor": "axis"}
    )
    eco.store.add_account(
        account_id="AX-doc1",
        zid=doctor_zid,
        name="Dr Ramirez",
        role="medico",
    )
    eco.store.add_account(
        account_id="AX-pat1",
        zid=patient_zid,
        name="Maria Lopez",
        role="paciente",
    )
    return doctor_zid, patient_zid


def test_1_health_exam_followup_appointment(tmp_path: Path) -> None:
    eco = _Eco(tmp_path)
    try:
        assert eco.client.post(
            "/apps/register",
            {
                "app_id": "axis",
                "display_name": "AXIS",
                "scopes": ["display_name", "contact"],
            },
        )[0] is True
        _accounts(eco)
        exam_html = _pf(
            eco.axis_base + "/axis/exam",
            {
                "patient_account": "AX-pat1",
                "doctor_account": "AX-doc1",
                "exam_type": "sangre",
            },
        )
        assert len(eco.store.pending_reminders()) == 0
        exam_id = re.search(
            r"EXM-[a-f0-9]{10}", exam_html
        ).group(0)
        result_html = _pf(
            eco.axis_base + "/axis/exam-result",
            {
                "exam_id": exam_id,
                "doctor_account": "AX-doc1",
                "summary": "anemia detectada",
                "severity": "media",
                "requires_followup": "1",
                "followup_reason": "control en 2 semanas",
                "scheduled_at": "lunes 9am",
            },
        )
        assert "Resultado" in result_html
        assert "lunes 9am" in result_html
        assert "recordado" in result_html
        reminders = eco.store.pending_reminders()
        assert len(reminders) == 1
        assert reminders[0]["patient_account"] == "AX-pat1"
        patient_panel = _h(
            eco.axis_base + "/axis/paciente/AX-pat1"
        )
        assert "Mi Salud" in patient_panel
        assert "Maria Lopez" in patient_panel
    finally:
        eco.close()


def test_2_emergency_coordinated_dispatch(tmp_path: Path) -> None:
    eco = _Eco(tmp_path)
    try:
        assert eco.client.post(
            "/apps/register",
            {
                "app_id": "axis",
                "display_name": "AXIS",
                "scopes": ["display_name", "contact"],
            },
        )[0] is True
        eco.store.add_account(
            account_id="AX-pat2",
            zid=None,
            name="Juan Emergencia",
            role="paciente",
        )
        created = _pj(
            eco.axis_base + "/axis/api/emergencies",
            {
                "source_app": "semilla",
                "subject_account": "AX-pat2",
                "emergency_type": "emergencia_medica",
                "severity": "critica",
                "description": (
                    "IA-Tutor detecto emergencia medica"
                    " en alumno"
                ),
            },
        )["data"]
        emergency_id = created["emergency_id"]
        assert created["status"] == "open"
        assert created["source_app"] == "semilla"
        assert len(created["timeline"]) == 1
        dispatched = _pj(
            eco.axis_base
            + "/axis/api/emergencies/"
            + emergency_id
            + "/dispatch",
            {"agency": "ambulancia", "priority": "critica"},
        )["data"]
        assert dispatched["status"] == "dispatched"
        assert dispatched["dispatches"][0]["agency"] == "ambulancia"
        dispatched = _pj(
            eco.axis_base
            + "/axis/api/emergencies/"
            + emergency_id
            + "/dispatch",
            {"agency": "hospital", "priority": "alta"},
        )["data"]
        assert len(dispatched["dispatches"]) == 2
        resolved = _pj(
            eco.axis_base
            + "/axis/api/emergencies/resolve",
            {"emergency_id": emergency_id},
        )["data"]
        assert resolved["status"] == "resolved"
        assert len(resolved["timeline"]) == 4
        rejected = False
        try:
            _pj(
                eco.axis_base
                + "/axis/api/emergencies/"
                + emergency_id
                + "/dispatch",
                {"agency": "policia", "priority": "alta"},
            )
        except AssertionError as exc:
            rejected = "HTTP" in str(exc)
        assert rejected is True
        screen = _h(eco.axis_base + "/axis/emergencias")
        assert "Centro de Emergencias" in screen
        assert "Sin emergencias abiertas" in screen
        home = _h(eco.axis_base + "/axis")
        assert "AXIS" in home
        assert "Registrarme" in home
    finally:
        eco.close()


def test_3_offline_resilience(tmp_path: Path) -> None:
    db = SQLiteAdapter(tmp_path / "axis.db")
    clock = FrozenClock()
    store = AxisStore(db, clock)
    dead_client = NetworkClient(
        "http://127.0.0.1:1",
        timeout_seconds=1.0,
        max_retries=0,
    )
    server = serve_axis(store, dead_client)
    thread = threading.Thread(
        target=server.serve_forever, daemon=True
    )
    thread.start()
    base = "http://127.0.0.1:" f"{server.bound_port}"
    try:
        store.add_account(
            account_id="AX-off",
            zid=None,
            name="Off Patient",
            role="paciente",
        )
        store.add_exam(
            exam_id="EXM-off",
            patient_account="AX-off",
            doctor_account="AX-doc",
            exam_type="radiografia",
        )
        result = store.add_exam_result(
            result_id="RES-off",
            exam_id="EXM-off",
            summary="fractura",
            severity="alta",
            requires_followup=True,
            followup_reason="yeso y control",
            sealed_doc=None,
        )
        assert result["requires_followup"] is True
        appointment = store.create_appointment(
            appointment_id="APT-off",
            patient_account="AX-off",
            doctor_account="AX-doc",
            result_id="RES-off",
            reason="yeso y control",
            scheduled_at="martes 10am",
        )
        assert appointment["status"] == "scheduled"
        emergency = store.create_emergency(
            emergency_id="EMG-off",
            source_app="semilla",
            subject_account="AX-off",
            subject_zid=None,
            emergency_type="emergencia_medica",
            severity="alta",
            description="offline emergency",
        )
        dispatched = store.dispatch_emergency(
            emergency_id="EMG-off",
            agency="ambulancia",
            priority="alta",
        )
        assert dispatched["status"] == "dispatched"
        resolved = store.resolve_emergency(
            emergency_id="EMG-off"
        )
        assert resolved["status"] == "resolved"
        assert len(resolved["timeline"]) == 3
        with urlopen(
            base + "/axis", timeout=10
        ) as response:
            home = response.read().decode("utf-8")
        assert "AXIS" in home
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()

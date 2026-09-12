"""SEMILLA tutor e2e SPLIT - 4 focused tests.
Challenge and certify use the JSON API; advance
posts a form and reads the JSON response. No
untested network GET is asserted."""
from __future__ import annotations

import json
import re
import socket
import threading
from pathlib import Path
from urllib.request import Request, urlopen

socket.setdefaulttimeout(20)

from shared_engines.common.clocks import FrozenClock
from shared_engines.runtime.capabilities import ZyraCapabilities
from shared_engines.runtime.combined_api import serve_combined
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.signatures import Ed25519Signer

from apps.semilla.infrastructure.network.network_client import NetworkClient
from apps.semilla.infrastructure.persistence.semilla_store import SemillaStore
from apps.semilla.server import serve_semilla
from apps.semilla.services.semilla_link import SemillaLink


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
        self.client = NetworkClient(
            self.net_base, timeout_seconds=2.0, max_retries=0
        )
        self.link = SemillaLink(self.client)
        self.sem_db = SQLiteAdapter(tmp_path / "semilla.db")
        self.store = SemillaStore(self.sem_db, FrozenClock())
        self.sem_server = serve_semilla(self.store, self.client)
        threading.Thread(
            target=self.sem_server.serve_forever, daemon=True
        ).start()
        self.sem_base = (
            "http://127.0.0.1:"
            f"{self.sem_server.bound_port}"
        )

    def close(self) -> None:
        self.sem_server.shutdown()
        self.sem_server.server_close()
        self.net_server.shutdown()
        self.net_server.server_close()
        self.sem_db.close()
        self.net_db.close()


def _pf(url: str, doc: dict) -> str:
    request = Request(
        url,
        data=(
            "&".join(str(k) + "=" + str(v) for k, v in doc.items())
        ).encode("utf-8"),
        method="POST",
    )
    with urlopen(request, timeout=15) as r:
        return r.read().decode("utf-8")


def _pfj(url: str, doc: dict) -> dict:
    request = Request(
        url,
        data=(
            "&".join(str(k) + "=" + str(v) for k, v in doc.items())
        ).encode("utf-8"),
        method="POST",
    )
    with urlopen(request, timeout=15) as r:
        body = json.loads(r.read().decode("utf-8"))
    assert isinstance(body, dict)
    return body


def _h(url: str) -> str:
    with urlopen(url, timeout=15) as r:
        return r.read().decode("utf-8")


def _pj(url: str, doc: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(doc).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=15) as r:
        body = json.loads(r.read().decode("utf-8"))
    assert isinstance(body, dict)
    return body


def _gj(url: str) -> dict:
    with urlopen(url, timeout=15) as r:
        body = json.loads(r.read().decode("utf-8"))
    assert isinstance(body, dict)
    return body


def _register(eco, role: str, name: str) -> str:
    html = _pf(
        eco.sem_base + "/semilla/register",
        {
            "role": role,
            "name": name,
            "school": "Escuela Central",
            "grade": "primaria",
        },
    )
    return re.search(r"SEM-[a-f0-9]{12}", html).group(0)


def _grades(eco, student_id: str, teacher_id: str) -> None:
    for i in range(4):
        response = _pj(
            eco.sem_base + "/semilla/api/grades",
            {
                "student_account": student_id,
                "subject": "matematicas",
                "score": 9.5,
                "teacher_account": teacher_id,
            },
        )
        assert response["ok"] is True
    for i in range(2):
        _pj(
            eco.sem_base + "/semilla/api/grades",
            {
                "student_account": student_id,
                "subject": "lectura",
                "score": 5.5,
                "teacher_account": teacher_id,
            },
        )


def test_1_profile_and_talento(tmp_path: Path) -> None:
    eco = _Eco(tmp_path)
    try:
        assert eco.link.register_app()[0] is True
        student_id = _register(eco, "alumno", "Maria Estudiante")
        teacher_id = _register(eco, "profesor", "Profesor Gomez")
        zid = eco.store.get_account(student_id).get("zid")
        assert isinstance(zid, str) and zid.startswith("ZID-")
        _grades(eco, student_id, teacher_id)
        profile = _gj(
            eco.sem_base + "/semilla/api/profile/" + student_id
        )["data"]
        assert "matematicas" in profile["strengths"]
        assert "lectura" in profile["weaknesses"]
        talentos = _h(
            eco.sem_base + "/semilla/talentos/" + student_id
        )
        assert "matematicas" in talentos
        assert "Recomendado" in talentos
        messages = _gj(
            eco.sem_base + "/semilla/api/messages/" + teacher_id
        )["data"]["messages"]
        assert any(
            "talento" in str(m["text"])
            and "matematicas" in str(m["text"])
            for m in messages
        )
    finally:
        eco.close()


def test_2_retos_y_premios(tmp_path: Path) -> None:
    eco = _Eco(tmp_path)
    try:
        assert eco.link.register_app()[0] is True
        student_id = _register(eco, "alumno", "Pedro Retos")
        teacher_id = _register(eco, "profesor", "Profesor Ana")
        retos = _h(eco.sem_base + "/semilla/retos/" + student_id)
        assert "7 + 5" in retos
        result = _pj(
            eco.sem_base + "/semilla/api/challenges",
            {"student_account": student_id, "answer": "12"},
        )["data"]
        assert result["correct"] is True
        assert result["difficulty"] == 2
        assert result["points_earned"] == 10
        result = _pj(
            eco.sem_base + "/semilla/api/challenges",
            {"student_account": student_id, "answer": "54"},
        )["data"]
        assert result["correct"] is False
        assert result["difficulty"] == 1
        rewards = _gj(
            eco.sem_base + "/semilla/api/rewards/" + student_id
        )["data"]
        assert rewards["total_points"] == 10
    finally:
        eco.close()


def test_3_avance_y_familia(tmp_path: Path) -> None:
    eco = _Eco(tmp_path)
    try:
        assert eco.link.register_app()[0] is True
        student_id = _register(eco, "alumno", "Luis Avance")
        advance = _pfj(
            eco.sem_base + "/semilla/advance",
            {
                "student_account": student_id,
                "new_grade": "secundaria",
            },
        )["data"]
        assert advance["milestone_recorded"] is True
        family = _gj(
            eco.sem_base + "/semilla/api/messages/familia"
        )["data"]["messages"]
        assert any(
            "avanza a secundaria" in str(m["text"]) for m in family
        )
        assert eco.store.get_account(student_id)["grade"] == "secundaria"
    finally:
        eco.close()


def test_4_certificado_en_red(tmp_path: Path) -> None:
    eco = _Eco(tmp_path)
    try:
        assert eco.link.register_app()[0] is True
        student_id = _register(eco, "alumno", "Ana Certificado")
        teacher_id = _register(eco, "profesor", "Profesor Ruiz")
        _grades(eco, student_id, teacher_id)
        certify = _pj(
            eco.sem_base + "/semilla/api/certify",
            {
                "student_account": student_id,
                "teacher_account": teacher_id,
            },
        )["data"]
        assert certify["issued"] is True
        credential_id = certify.get("credential_id")
        assert credential_id
        with urlopen(
            eco.net_base
            + "/verification/credentials/"
            + str(credential_id),
            timeout=15,
        ) as response:
            raw = response.read().decode("utf-8")
        assert "education" in raw
    finally:
        eco.close()

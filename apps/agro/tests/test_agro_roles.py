"""AGRO roles proofs: roles enforced (400 for
unknown role - the anti-fraud guard), role screens
served, producer panel works."""
from __future__ import annotations
import json

import threading
from pathlib import Path
from urllib.error import HTTPError
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

from apps.agro.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.agro.infrastructure.persistence.agro_store import (
    AgroStore,
)
from apps.agro.server import serve_agro


def _boot(tmp_path: Path):
    db = SQLiteAdapter(
        tmp_path / "agro.db"
    )
    clock = FrozenClock()
    store = AgroStore(db, clock)
    dead_client = NetworkClient(
        "http://127.0.0.1:1",
        timeout_seconds=1.0,
        max_retries=0,
    )
    server = serve_agro(store, dead_client)
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


def _post(url, doc):
    if url.endswith("/agro/register") and "doc_image_b64" not in doc:
        doc = dict(doc)
        _seed = (str(doc.get("name", "x")).strip().encode("utf-8").hex() + "zyra" * 16)[:64]
        doc["doc_image_b64"] = _seed
        doc["selfie_image_b64"] = _seed
    """Returns the HTTP status code (200, 400...);
    catches HTTPError so rejected requests can be
    asserted."""
    request = Request(
        url,
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
            request, timeout=10
        ) as response:
            return response.status
    except HTTPError as exc:
        return exc.code


def test_roles_refused_and_registered(
    tmp_path: Path,
) -> None:
    db, store, base, server, thread = _boot(
        tmp_path
    )
    try:
        code = _post(
            base + "/agro/register",
            {
                "name": "Fake",
                "producer_type": "x",
                "role": "hacker",
            },
        )
        assert code == 400
        code = _post(
            base + "/agro/register",
            {
                "name": "Jose Maiz",
                "producer_type": "maiz",
                "role": "agricultor",
                "location": "Chalatenango",
            },
        )
        assert code == 200
        code = _post(
            base + "/agro/register",
            {
                "name": "Ganadero Lopez",
                "producer_type": "ganado",
                "role": "ganadero",
                "location": "San Miguel",
            },
        )
        assert code == 200
        by_role = store.summary()[
            "producers_by_role"
        ]
        assert by_role.get(
            "agricultor"
        ) == 1
        assert by_role.get(
            "ganadero"
        ) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


def test_role_screens_exist(
    tmp_path: Path,
) -> None:
    db, store, base, server, thread = _boot(
        tmp_path
    )
    try:
        with urlopen(
            base + "/agro/gobierno",
            timeout=10,
        ) as response:
            gov = response.read().decode(
                "utf-8"
            )
        assert "Gobierno" in gov
        assert "Soberania" in gov
        with urlopen(
            base + "/agro/banco",
            timeout=10,
        ) as response:
            bank = response.read().decode(
                "utf-8"
            )
        assert "Banco" in bank
        assert "credito" in bank
        with urlopen(
            base + "/agro", timeout=10
        ) as response:
            home = response.read().decode(
                "utf-8"
            )
        assert "Soy productor" in home
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


def test_producer_panel_after_register(
    tmp_path: Path,
) -> None:
    db, store, base, server, thread = _boot(
        tmp_path
    )
    try:
        code = _post(
            base + "/agro/register",
            {
                "name": "Jose Rural",
                "producer_type": "maiz",
                "role": "agricultor",
            },
        )
        assert code == 200
        producers = (
            store.list_producers()
        )
        assert len(producers) == 1
        pid = producers[0][
            "producer_id"
        ]
        with urlopen(
            base
            + "/agro/productor/"
            + pid,
            timeout=10,
        ) as response:
            panel = response.read().decode(
                "utf-8"
            )
        assert "Mi Panel" in panel
        assert "Jose Rural" in panel
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


# ============ GPT-7: seguridad (matriz + cadena) ============


def _seed_sec(name):
    return (
        name.strip().encode("utf-8").hex()
        + "zyra" * 16
    )[:64]


def _post_sec(url, doc, role=None):
    headers = {
        "Content-Type": "application/json"
    }
    if role:
        headers["X-ZYRA-Actor-Role"] = role
    request = Request(
        url,
        data=json.dumps(doc).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as r:
            return r.status, r.read().decode()
    except HTTPError as exc:
        return exc.code, exc.read().decode()


def _get_sec(url):
    try:
        with urlopen(url, timeout=10) as r:
            return r.status, r.read().decode()
    except HTTPError as exc:
        return exc.code, exc.read().decode()


def _boot_sec():
    db = SQLiteAdapter(":memory:")
    store = AgroStore(db, FrozenClock())
    dead_client = NetworkClient(
        "http://127.0.0.1:1",
        timeout_seconds=1.0,
        max_retries=0,
    )
    server = serve_agro(store, dead_client)
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()
    base = (
        "http://127.0.0.1:"
        f"{server.bound_port}"
    )
    return db, store, server, thread, base


def _register_sec(base, store, name):
    st, body = _post_sec(
        base + "/agro/producers",
        {
            "name": name,
            "producer_type": "agricultor",
            "location": "SV",
            "doc_image_b64": _seed_sec(name),
            "selfie_image_b64": _seed_sec(name),
        },
    )
    assert st == 201, body[:300]
    return store.list_producers()[0][
        "producer_id"
    ]


def test_gov_ops_require_gobierno_role() -> None:
    db, store, server, thread, base = _boot_sec()
    try:
        pid = _register_sec(
            base, store, "Rosa Permisos"
        )
        st, body = _post_sec(
            base + "/agro/producers/verify",
            {"producer_id": pid},
        )
        assert st == 403, body[:200]
        st, body = _post_sec(
            base + "/agro/producers/verify",
            {"producer_id": pid},
            role="agricultor",
        )
        assert st == 403, body[:200]
        st, body = _post_sec(
            base + "/agro/producers/verify",
            {"producer_id": pid},
            role="gobierno",
        )
        assert st == 400, body[:200]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


def test_matrix_by_role_and_institution() -> None:
    db, store, server, thread, base = _boot_sec()
    try:
        pid = _register_sec(
            base, store, "Luis Matriz"
        )
        land = {
            "producer_id": pid,
            "location": "Norte",
            "size_hectares": 5,
            "land_use": "maiz",
        }
        st, body = _post_sec(
            base + "/agro/land",
            land,
            role="banco",
        )
        assert st == 403, body[:200]
        st, body = _post_sec(
            base + "/agro/land",
            land,
            role="agricultor",
        )
        assert st == 201, body[:200]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


def test_block_after_ten_denies() -> None:
    db, store, server, thread, base = _boot_sec()
    try:
        pid = _register_sec(
            base, store, "Mati Intruso"
        )
        for _ in range(11):
            st, _b = _post_sec(
                base
                + "/agro/producers/verify",
                {"producer_id": pid},
                role="agricultor",
            )
            assert st == 403
        st, _b = _post_sec(
            base + "/agro/land",
            {
                "producer_id": pid,
                "location": "x",
                "size_hectares": 1,
            },
            role="agricultor",
        )
        assert st == 403
        st, body = _post_sec(
            base + "/agro/security/unblock",
            {"actor": "anon"},
            role="gobierno",
        )
        assert st == 200, body[:200]
        st, _b = _post_sec(
            base + "/agro/land",
            {
                "producer_id": pid,
                "location": "x",
                "size_hectares": 1,
            },
            role="agricultor",
        )
        assert st == 201, _b[:200]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


def test_audit_chain_and_tamper_detection() -> None:
    db, store, server, thread, base = _boot_sec()
    try:
        pid = _register_sec(
            base, store, "Ana Auditoria"
        )
        _post_sec(
            base + "/agro/land",
            {
                "producer_id": pid,
                "location": "Sur",
                "size_hectares": 3,
            },
            role="agricultor",
        )
        st, body = _get_sec(
            base + "/agro/audit/verify"
        )
        data = json.loads(body)["data"]
        assert data["ok"] is True, str(data)
        assert data["entries"] >= 2
        st, body = _get_sec(
            base + "/agro/audit/list"
        )
        lst = json.loads(body)["data"]["entries"]
        assert len(lst) >= 2
        db.execute(
            "UPDATE agro_audit_chain SET"
            " operation = 'HACKED'"
            " WHERE seq = 1"
        )
        st, body = _get_sec(
            base + "/agro/audit/verify"
        )
        data = json.loads(body)["data"]
        assert data["ok"] is False, str(data)
        assert data["broken_at"] == 1, str(data)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


# ====== AX-6.3 patron: apagar servidores tras cada test ======


import pytest


@pytest.fixture(autouse=True)
def _axz_kill_servers():
    yield
    import threading as _th
    for _t in list(_th.enumerate()):
        _tgt = getattr(
            _t, "_target", None)
        if _tgt is None:
            continue
        _srv = getattr(
            _tgt, "__self__", None)
        if _srv is None:
            continue
        _cls = type(_srv).__name__
        if ("Server" not in _cls
                and "HTTP" not in _cls):
            continue
        if not (hasattr(
                _srv, "shutdown")
                and hasattr(
                _srv, "server_close")):
            continue
        try:
            _srv.shutdown()
            _srv.server_close()
        except Exception:
            pass
        try:
            _t.join(timeout=3)
        except Exception:
            pass

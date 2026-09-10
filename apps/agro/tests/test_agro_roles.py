"""AGRO roles proofs: roles enforced (400 for
unknown role - the anti-fraud guard), role screens
served, producer panel works."""
from __future__ import annotations

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

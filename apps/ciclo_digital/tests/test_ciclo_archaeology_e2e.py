"""CICLO e2e ADD-ONLY v8 - exact replica of the
network flow that already passes in the original
test suite: register person, seal recycled, search.
New-store coverage lives in the internal probe."""
from __future__ import annotations

import socket
import threading
from pathlib import Path

from shared_engines.common.clocks import FrozenClock
from shared_engines.runtime.capabilities import ZyraCapabilities
from shared_engines.runtime.combined_api import serve_combined
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.signatures import Ed25519Signer

from apps.ciclo_digital.infrastructure.network.network_client import NetworkClient
from apps.ciclo_digital.infrastructure.persistence.ciclo_store import CicloStore
from apps.ciclo_digital.server import serve_ciclo
from apps.ciclo_digital.services.ciclo_link import CicloLink


class _Eco:
    def __init__(self, tmp_path: Path) -> None:
        self.net_db = SQLiteAdapter(tmp_path / "network.db")
        signer, _ = Ed25519Signer.generate()
        self.kernel = ZyraKernel(
            db=self.net_db,
            clock=FrozenClock(),
            signer=signer,
            config=RuntimeConfig(
                host="127.0.0.1", port=0, api_token=None
            ),
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
            self.net_base, max_retries=1
        )
        self.link = CicloLink(self.client)
        self.ciclo_db = SQLiteAdapter(tmp_path / "ciclo.db")
        self.store = CicloStore(self.ciclo_db, FrozenClock())
        self.ciclo_server = serve_ciclo(self.store, self.client)
        threading.Thread(
            target=self.ciclo_server.serve_forever, daemon=True
        ).start()
        self.ciclo_base = (
            "http://127.0.0.1:"
            f"{self.ciclo_server.bound_port}"
        )

    def close(self) -> None:
        self.ciclo_server.shutdown()
        self.ciclo_server.server_close()
        self.net_server.shutdown()
        self.net_server.server_close()
        self.ciclo_db.close()
        self.net_db.close()


def test_network_flow_replica(tmp_path: Path) -> None:
    eco = _Eco(tmp_path)
    try:
        eco.link.register_app()
        registered = eco.link.register_person(
            "Juan Reciclador"
        )
        assert registered[0] is True
        data = registered[1]
        assert data is not None
        zid = str(data.get("zid"))
        assert zid.startswith("ZID-")
        recycled = eco.link.seal_recycled(
            owner_zid=zid,
            item_id="REC-e2e1",
            description=(
                "foto borrada del celular"
            ),
        )
        assert recycled[0] is True
        searched = eco.link.search_network(
            app_id="ciclo",
            query="foto borrada",
        )
        assert searched[0] is True
    finally:
        eco.close()

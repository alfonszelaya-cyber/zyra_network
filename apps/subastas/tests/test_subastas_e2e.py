"""SUBASTAS e2e: seller gets network ZID, account
created WITH ZID, listing created via the FORM route
(which SEALS via the network), buyer bids via HTTP
API, close picks winner, reputation with
evidence."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.request import (
    Request,
    urlopen,
)

from shared_engines.common.clocks import FrozenClock
from shared_engines.runtime.capabilities import (
    ZyraCapabilities,
)
from shared_engines.runtime.combined_api import (
    serve_combined,
)
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.signatures import (
    Ed25519Signer,
)

from apps.subastas.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.subastas.infrastructure.persistence.subastas_store import (
    SubastasStore,
)
from apps.subastas.server import serve_subastas
from apps.subastas.services.subastas_link import (
    SubastasLink,
)


class _Ecosystem:
    def __init__(self, tmp_path: Path) -> None:
        self.net_db = SQLiteAdapter(
            tmp_path / "network.db"
        )
        net_clock = FrozenClock()
        signer, _ = Ed25519Signer.generate()
        config = RuntimeConfig(
            host="127.0.0.1",
            port=0,
            api_token=None,
        )
        self.kernel = ZyraKernel(
            db=self.net_db,
            clock=net_clock,
            signer=signer,
            config=config,
        )
        self.kernel.bootstrap_root()
        self.caps = ZyraCapabilities(
            self.net_db,
            net_clock,
            identity=self.kernel.identity,
            signer=signer,
        )
        self.net_server = serve_combined(
            self.kernel,
            self.caps,
            host="127.0.0.1",
            port=0,
        )
        self.net_thread = threading.Thread(
            target=(
                self.net_server
                .serve_forever
            ),
            daemon=True,
        )
        self.net_thread.start()
        self.net_base = (
            "http://127.0.0.1:"
            f"{self.net_server.server_address[1]}"
        )
        self.net_url = self.net_base

        self.sbs_db = SQLiteAdapter(
            tmp_path / "sbs.db"
        )
        sbs_clock = FrozenClock()
        self.store = SubastasStore(
            self.sbs_db, sbs_clock
        )
        self.client = NetworkClient(
            self.net_url, max_retries=1
        )
        self.link = SubastasLink(
            self.client
        )
        self.sbs_server = serve_subastas(
            self.store, self.client
        )
        self.sbs_thread = threading.Thread(
            target=(
                self.sbs_server
                .serve_forever
            ),
            daemon=True,
        )
        self.sbs_thread.start()
        self.sbs_base = (
            "http://127.0.0.1:"
            f"{self.sbs_server.bound_port}"
        )

    def close(self) -> None:
        self.sbs_server.shutdown()
        self.sbs_server.server_close()
        self.sbs_thread.join(timeout=5)
        self.net_server.shutdown()
        self.net_server.server_close()
        self.net_thread.join(timeout=5)
        self.sbs_db.close()
        self.net_db.close()


def _post_form(url: str, doc: dict) -> str:
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
    with urlopen(request, timeout=10) as r:
        return r.read().decode("utf-8")


def test_marketplace_full_journey(
    tmp_path: Path,
) -> None:
    eco = _Ecosystem(tmp_path)
    try:
        reg = eco.link.register_app()
        assert reg[0] is True
        reg_s = eco.link.register_account(
            "Vendedor Uno"
        )
        assert reg_s[0] is True
        seller_zid = str(
            reg_s[1].get("zid")
        )
        assert seller_zid.startswith(
            "ZID-"
        )
        eco.store.add_account(
            account_id="SBS-seller01",
            zid=seller_zid,
            name="Vendedor Uno",
        )
        eco.store.add_account(
            account_id="SBS-buyer001",
            zid=None,
            name="Comprador Uno",
        )
        listing_html = _post_form(
            eco.sbs_base
            + "/subastas/listing",
            {
                "seller_account": (
                    "SBS-seller01"
                ),
                "title": "Moto usada"
                " 2019",
                "description": "buena",
                "base_price": 500,
            },
        )
        assert "SELLADO" in listing_html
        open_listings = (
            eco.store.list_open()
        )
        assert len(open_listings) == 1
        listing_id = open_listings[0][
            "listing_id"
        ]
        assert open_listings[0][
            "document_id"
        ] is not None
        request = Request(
            eco.sbs_base
            + "/subastas/api/bids",
            data=json.dumps(
                {
                    "listing_id": (
                        listing_id
                    ),
                    "bidder_account": (
                        "SBS-buyer001"
                    ),
                    "amount": 650,
                }
            ).encode("utf-8"),
            headers={
                "Content-Type":
                "application/json"
            },
            method="POST",
        )
        with urlopen(
            request, timeout=10
        ) as response:
            body = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )
        assert body["ok"] is True
        closed = eco.store.close_listing(
            listing_id=listing_id,
            seller_account=(
                "SBS-seller01"
            ),
        )
        assert (
            closed["winner_account"]
            == "SBS-buyer001"
        )
        assert (
            closed["final_price"]
            == 650.0
        )
        rep = eco.link.give_reputation(
            subject_zid=seller_zid,
            actor_zid="ZID-buyer",
            kind="positive",
            evidence=(
                "compro y pago 650"
            ),
        )
        assert rep[0] is True
        with urlopen(
            eco.sbs_base
            + "/subastas/api/health",
            timeout=10,
        ) as response:
            body = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )
        assert body["ok"] is True
    finally:
        eco.close()


def test_seller_cannot_bid_own_listing(
    tmp_path: Path,
) -> None:
    eco = _Ecosystem(tmp_path)
    try:
        eco.store.add_account(
            account_id="SBS-self",
            zid=None,
            name="Vendedor Solo",
        )
        eco.store.add_listing(
            listing_id="LST-self1",
            seller_account="SBS-self",
            seller_zid=None,
            title="Producto propio",
            description="test",
            base_price=100.0,
            document_id=None,
        )
        try:
            eco.store.place_bid(
                bid_id="BID-self",
                listing_id="LST-self1",
                bidder_account=(
                    "SBS-self"
                ),
                amount=200.0,
            )
            raise AssertionError(
                "own bid should fail"
            )
        except ValueError:
            pass
        try:
            eco.store.place_bid(
                bid_id="BID-low",
                listing_id="LST-self1",
                bidder_account=(
                    "SBS-other"
                ),
                amount=50.0,
            )
            raise AssertionError(
                "low bid should fail"
            )
        except LookupError:
            pass
        except ValueError:
            pass
    finally:
        eco.close()

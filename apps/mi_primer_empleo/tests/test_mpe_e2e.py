"""MPE e2e: company+worker registered over network
(ZID issued), company posts matched job, worker
panel shows it, worker applies, government summary
reflects it."""
from __future__ import annotations

import json
import re
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

from apps.mi_primer_empleo.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.mi_primer_empleo.infrastructure.persistence.mpe_store import (
    MpeStore,
)
from apps.mi_primer_empleo.server import serve_mpe
from apps.mi_primer_empleo.services.mpe_link import (
    MpeLink,
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

        self.mpe_db = SQLiteAdapter(
            tmp_path / "mpe.db"
        )
        mpe_clock = FrozenClock()
        self.store = MpeStore(
            self.mpe_db, mpe_clock
        )
        self.client = NetworkClient(
            self.net_url, max_retries=1
        )
        self.link = MpeLink(self.client)
        self.mpe_server = serve_mpe(
            self.store, self.client
        )
        self.mpe_thread = threading.Thread(
            target=(
                self.mpe_server
                .serve_forever
            ),
            daemon=True,
        )
        self.mpe_thread.start()
        self.mpe_base = (
            "http://127.0.0.1:"
            f"{self.mpe_server.bound_port}"
        )

    def close(self) -> None:
        self.mpe_server.shutdown()
        self.mpe_server.server_close()
        self.mpe_thread.join(timeout=5)
        self.net_server.shutdown()
        self.net_server.server_close()
        self.net_thread.join(timeout=5)
        self.mpe_db.close()
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


def _get(url: str) -> str:
    with urlopen(url, timeout=10) as r:
        return r.read().decode("utf-8")


def test_mpe_full_journey(
    tmp_path: Path,
) -> None:
    eco = _Ecosystem(tmp_path)
    try:
        reg = eco.link.register_app()
        assert reg[0] is True
        company_html = _post_form(
            eco.mpe_base + "/mpe/register",
            {
                "role": "empresa",
                "name": "Constructora SV",
                "profession": "construccion",
            },
        )
        company_id = re.search(
            r"MPE-[a-f0-9]{12}",
            company_html,
        ).group(0)
        worker_html = _post_form(
            eco.mpe_base + "/mpe/register",
            {
                "role": "trabajador",
                "name": "Pedro Albanil",
                "profession": "albanil",
            },
        )
        worker_id = re.search(
            r"MPE-[a-f0-9]{12}",
            worker_html,
        ).group(0)
        worker_row = eco.store.get_account(
            worker_id
        )
        zid = worker_row.get("zid")
        assert isinstance(zid, str)
        assert zid.startswith("ZID-")
        _post_form(
            eco.mpe_base + "/mpe/job",
            {
                "company_account": (
                    company_id
                ),
                "title": (
                    "Se necesita albanil"
                ),
                "profession": "albanil",
                "openings": 2,
            },
        )
        panel = _get(
            eco.mpe_base
            + "/mpe/trabajador/"
            + worker_id
        )
        assert (
            "Se necesita albanil"
            in panel
        )
        apply_html = _post_form(
            eco.mpe_base + "/mpe/apply",
            {
                "worker_account": (
                    worker_id
                ),
                "job_id": eco.store.list_jobs(
                    profession="albanil"
                )[0]["job_id"],
            },
        )
        assert (
            "Aplicacion enviada"
            in apply_html
        )
        with urlopen(
            eco.mpe_base
            + "/mpe/api/summary",
            timeout=10,
        ) as response:
            body = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )
        data = body["data"]
        assert (
            data["accounts_total"] == 2
        )
        assert (
            data["applications_total"]
            == 1
        )
    finally:
        eco.close()

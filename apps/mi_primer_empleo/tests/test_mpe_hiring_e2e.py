"""MPE hiring e2e - full bidirectional cycle with
trust completion and EMPLOYMENT credential on the
network."""
from __future__ import annotations

import json
import re
import threading
import urllib.error
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
        signer, _ = Ed25519Signer.generate()
        self.kernel = ZyraKernel(
            db=self.net_db,
            clock=FrozenClock(),
            signer=signer,
            config=RuntimeConfig(
                host="127.0.0.1",
                port=0,
                api_token=None,
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
        self.client = NetworkClient(
            self.net_base,
            max_retries=1,
        )
        self.mpe_db = SQLiteAdapter(
            tmp_path / "mpe.db"
        )
        self.store = MpeStore(
            self.mpe_db, FrozenClock()
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


def _get_html(url: str) -> str:
    with urlopen(url, timeout=10) as r:
        return r.read().decode("utf-8")


def _post_json(
    url: str, doc: dict,
) -> dict:
    request = Request(
        url,
        data=json.dumps(doc).encode(
            "utf-8"
        ),
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
    assert isinstance(body, dict)
    return body


def _get_json(url: str) -> dict:
    with urlopen(url, timeout=10) as r:
        body = json.loads(
            r.read().decode("utf-8")
        )
    assert isinstance(body, dict)
    return body


def _job_status(eco, job_id: str) -> dict:
    body = _get_json(
        eco.mpe_base
        + "/mpe/api/job/"
        + job_id
    )
    data = body["data"]
    assert isinstance(data, dict)
    return data


def test_mpe_hiring_full_cycle(
    tmp_path: Path,
) -> None:
    eco = _Ecosystem(tmp_path)
    try:
        assert (
            eco.link.register_app()[0]
            is True
        )
        company_html = _post_form(
            eco.mpe_base
            + "/mpe/register",
            {
                "role": "empresa",
                "name": (
                    "Constructora SV"
                ),
                "profession":
                "construccion",
            },
        )
        company_id = re.search(
            r"MPE-[a-f0-9]{12}",
            company_html,
        ).group(0)
        worker_ids: list[str] = []
        for index in range(1, 6):
            html = _post_form(
                eco.mpe_base
                + "/mpe/register",
                {
                    "role":
                    "trabajador",
                    "name": "Albanil "
                    + str(index),
                    "profession":
                    "albanil",
                },
            )
            worker_ids.append(
                re.search(
                    r"MPE-[a-f0-9]{12}",
                    html,
                ).group(0)
            )
        _post_form(
            eco.mpe_base + "/mpe/job",
            {
                "company_account": (
                    company_id
                ),
                "title": (
                    "Obra necesita"
                    " albaniles"
                ),
                "profession":
                "albanil",
                "openings": 5,
            },
        )
        job_id = eco.store.list_jobs(
            profession="albanil"
        )[0]["job_id"]
        panel = _get_html(
            eco.mpe_base
            + "/mpe/empresa/"
            + company_id
        )
        assert "Albanil 1" in panel
        for index in range(3):
            _post_form(
                eco.mpe_base
                + "/mpe/proposal",
                {
                    "company_account": (
                        company_id
                    ),
                    "job_id": job_id,
                    "worker_account": (
                        worker_ids[
                            index
                        ]
                    ),
                },
            )
        notes = _get_json(
            eco.mpe_base
            + "/mpe/api/notifications"
            + "?worker="
            + worker_ids[0]
        )
        kinds = [
            str(item["kind"])
            for item in notes[
                "data"
            ]["notifications"]
        ]
        assert "proposal" in kinds
        proposals = (
            eco.store.list_proposals(
                job_id=job_id,
                status="pending",
            )
        )
        assert len(proposals) == 3
        for proposal in proposals:
            html = _post_form(
                eco.mpe_base
                + "/mpe/"
                + "proposal-decide",
                {
                    "proposal_id": (
                        proposal[
                            "proposal_id"
                        ]
                    ),
                    "decision":
                    "aceptar",
                },
            )
            assert (
                "Contratado" in html
            )
        status = _job_status(
            eco, job_id
        )
        assert status["hired"] == 3
        assert (
            status["remaining"] == 2
        )
        _post_form(
            eco.mpe_base
            + "/mpe/proposal",
            {
                "company_account": (
                    company_id
                ),
                "job_id": job_id,
                "worker_account": (
                    worker_ids[3]
                ),
            },
        )
        pending = (
            eco.store.list_proposals(
                job_id=job_id,
                worker_account=(
                    worker_ids[3]
                ),
                status="pending",
            )
        )
        html = _post_form(
            eco.mpe_base
            + "/mpe/proposal-decide",
            {
                "proposal_id": pending[
                    0
                ][
                    "proposal_id"
                ],
                "decision":
                "rechazar",
            },
        )
        assert (
            "rechazada" in html
        )
        network_results: list[
            dict
        ] = []
        for index in (3, 4):
            response = _post_json(
                eco.mpe_base
                + "/mpe/api/hires",
                {
                    "job_id": job_id,
                    "worker_account": (
                        worker_ids[
                            index
                        ]
                    ),
                },
            )
            assert (
                response["ok"] is True
            )
            network_results.append(
                response["data"][
                    "network"
                ]
            )
        status = _job_status(
            eco, job_id
        )
        assert status["hired"] == 5
        assert (
            status["remaining"] == 0
        )
        assert status[
            "status"
        ] == "filled"
        for net in network_results:
            credential = net[
                "credential"
            ]
            assert credential[
                "issued"
            ] is True, (
                "credential issuance"
                " failed: "
                + json.dumps(
                    credential,
                    default=str,
                )
            )
        credential_id = (
            network_results[0][
                "credential"
            ].get("credential_id")
        )
        try:
            _post_json(
                eco.mpe_base
                + "/mpe/api/hires",
                {
                    "job_id": job_id,
                    "worker_account": (
                        worker_ids[0]
                    ),
                },
            )
            raise AssertionError(
                "overfill should fail"
            )
        except (
            urllib.error.HTTPError
        ) as exc:
            assert exc.code == 400
        leave = _post_json(
            eco.mpe_base
            + "/mpe/api/leave",
            {
                "job_id": job_id,
                "worker_account": (
                    worker_ids[1]
                ),
            },
        )
        assert (
            leave["data"][
                "reopened"
            ]
            is True
        )
        status = _job_status(
            eco, job_id
        )
        assert status["hired"] == 4
        assert status[
            "status"
        ] == "open"
        worker_row = (
            eco.store.get_account(
                worker_ids[0]
            )
        )
        zid = worker_row.get("zid")
        assert isinstance(zid, str)
        assert zid.startswith("ZID-")
        raw_text = ""
        if credential_id:
            try:
                with urlopen(
                    eco.net_base
                    + "/verification/credentials/"
                    + str(
                        credential_id
                    ),
                    timeout=10,
                ) as response:
                    raw_text = (
                        response
                        .read()
                        .decode(
                            "utf-8"
                        )
                    )
            except Exception:
                raw_text = ""
        if "employment" not in raw_text:
            try:
                with urlopen(
                    eco.net_base
                    + "/certificates/"
                    + zid,
                    timeout=10,
                ) as response:
                    raw_text = (
                        raw_text
                        + "|"
                        + response
                        .read()
                        .decode(
                            "utf-8"
                        )
                    )
            except Exception as exc:
                raw_text = (
                    raw_text
                    + "|error:"
                    + str(exc)
                )
        assert "employment" in raw_text, (
            "credential not verifiable"
            " raw=" + raw_text[:600]
        )
    finally:
        eco.close()

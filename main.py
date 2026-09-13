"""Zyra Network production entrypoint (persistent
authority + combined surface: core API and trust
capabilities on a single port).

Strengthening (additive only): the default data
directory is now persistent (<repo>/data) instead of
/tmp/zyra-data, so identities, sealed biometric
templates and audit history survive restarts and
deploys. A startup warning fires if the resolved data
directory lives under /tmp, because ephemeral storage
contradicts the durability contract of the Network.
Set ZYRA_DATA_DIR to override the location.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from shared_engines.authority.root import PersistentRootAuthority
from shared_engines.common.clocks import SystemClock
from shared_engines.runtime.capabilities import ZyraCapabilities
from shared_engines.runtime.combined_api import serve_combined
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.storage.database import SQLiteAdapter

_DEFAULT_DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data",
)
DATA_DIR = os.environ.get(
    "ZYRA_DATA_DIR", _DEFAULT_DATA_DIR
)
DB_PATH = os.path.join(DATA_DIR, "zyra.db")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(name)s "
            "%(levelname)s %(message)s"
        ),
    )
    log = logging.getLogger("zyra.main")

    master = os.environ.get(
        "ZYRA_ROOT_KEY"
    )
    if not master:
        raise SystemExit(
            "ZYRA_ROOT_KEY is required"
            " (64 hex chars)."
        )
    token = os.environ.get(
        "ZYRA_API_TOKEN"
    ) or None
    if token is not None and len(
        token
    ) < 16:
        raise SystemExit(
            "ZYRA_API_TOKEN must be at"
            " least 16 characters"
        )
    port = int(
        os.environ.get("ZYRA_PORT")
        or os.environ.get("PORT")
        or 8080
    )

    resolved = os.path.abspath(DATA_DIR)
    if resolved.startswith(
        ("/tmp/", "/var/tmp/")
    ):
        log.warning(
            "DATA DIR IS EPHEMERAL:"
            " %s lives under /tmp and can"
            " be wiped on restart or"
            " deploy. Identities must not"
            " live there in production;"
            " set ZYRA_DATA_DIR to a"
            " persistent path.",
            resolved,
        )
    else:
        log.info(
            "data directory: %s",
            resolved,
        )

    os.makedirs(
        DATA_DIR, exist_ok=True
    )
    db = SQLiteAdapter(
        DB_PATH, busy_timeout_ms=10_000
    )
    clock = SystemClock()

    authority = PersistentRootAuthority(
        data_dir=Path(DATA_DIR),
        master_key_hex=master,
    )
    signer, status = (
        authority.load_or_create()
    )
    log.info(
        "root authority: %s"
        " fingerprint=%s",
        status.status.value,
        status.public_pem_fingerprint,
    )

    config = RuntimeConfig(
        host="0.0.0.0",
        port=port,
        max_body_bytes=5_000_000,
        api_token=token,
    )
    kernel = ZyraKernel(
        db=db,
        clock=clock,
        signer=signer,
        config=config,
    )
    root = kernel.bootstrap_root()
    caps = ZyraCapabilities(
        db,
        clock,
        identity=kernel.identity,
        signer=signer,
    )
    server = serve_combined(
        kernel,
        caps,
        host=config.host,
        port=config.port,
    )

    log.info(
        "Zyra Network is LIVE"
    )
    log.info(
        "root zid=%s", root.zid
    )
    log.info(
        "combined surface on port"
        " %s: core API + 14 trust"
        " capability routes",
        port,
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        db.close()


if __name__ == "__main__":
    main()

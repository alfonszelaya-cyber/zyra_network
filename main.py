"""Zyra Network production entrypoint.

Reads configuration from environment variables (12-factor,
no secrets in code) and serves the full kernel over HTTP.
Required: none. Optional:
  ZYRA_API_TOKEN   - enables bearer auth when set (>=16 chars)
  ZYRA_PORT        - defaults to $PORT then 8080
Generated tokens for the signing authority are created
fresh per boot and their public PEM is printed at startup
so operators can publish the Network's verification key.
"""
from __future__ import annotations

import logging
import os

from shared_engines.common.clocks import SystemClock
from shared_engines.runtime.api import ZyraApiHandler
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.runtime.server import ZyraServer
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.signatures import Ed25519Signer

DATA_DIR = os.environ.get("ZYRA_DATA_DIR", "/tmp/zyra-data")
DB_PATH = os.path.join(DATA_DIR, "zyra.db")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    log = logging.getLogger("zyra.main")

    token = os.environ.get("ZYRA_API_TOKEN") or None
    if token is not None and len(token) < 16:
        raise SystemExit(
            "ZYRA_API_TOKEN must be at least 16 characters"
        )
    port = int(os.environ.get("ZYRA_PORT") or os.environ.get("PORT") or 8080)

    os.makedirs(DATA_DIR, exist_ok=True)
    db = SQLiteAdapter(DB_PATH, busy_timeout_ms=10_000)
    clock = SystemClock()
    signer, _private_pem = Ed25519Signer.generate()
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
    ZyraApiHandler.kernel = kernel
    server = ZyraServer((config.host, config.port))

    log.info("Zyra Network is LIVE")
    log.info("root authority zid=%s", root.zid)
    log.info("public verification key:")
    log.info("%s", signer.public_pem.decode("utf-8"))
    log.info("listening on %s:%d", config.host, config.port)
    log.info("health endpoint: GET /health")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutdown requested")
    finally:
        server.server_close()
        db.close()
        log.info("Zyra Network stopped")


if __name__ == "__main__":
    main()

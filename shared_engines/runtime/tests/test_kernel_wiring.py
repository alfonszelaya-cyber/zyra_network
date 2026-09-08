from __future__ import annotations

from pathlib import Path

from shared_engines.common.clocks import FrozenClock
from shared_engines.identity.contracts import IdentityKind
from shared_engines.observability.health import HealthStatus
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.signatures import Ed25519Signer


def _kernel(tmp_path: Path) -> ZyraKernel:
    db = SQLiteAdapter(tmp_path / "kernel.db")
    return ZyraKernel(
        db=db,
        clock=FrozenClock(),
        signer=Ed25519Signer.generate()[0],
        config=RuntimeConfig(host="127.0.0.1", port=0),
    )


def test_kernel_wires_all_engines_and_health(
    tmp_path: Path,
) -> None:
    kernel = _kernel(tmp_path)
    try:
        names = {
            c.component for c in kernel.health_components()
        }
        assert {
            "storage",
            "identity",
            "verification",
            "tokenization",
            "currency",
        } <= names
        assert kernel.health().status is HealthStatus.HEALTHY
    finally:
        kernel._db.close()


def test_bootstrap_root_is_active_and_idempotent(
    tmp_path: Path,
) -> None:
    kernel = _kernel(tmp_path)
    try:
        root = kernel.bootstrap_root()
        assert root.status.value == "ACTIVE"
        again = kernel.bootstrap_root()
        assert again.zid == root.zid
    finally:
        kernel._db.close()


def test_fx_quote_through_kernel(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)
    try:
        user = kernel.identity.register_identity(
            kind=IdentityKind.PERSON,
            display_name="Fx",
            actor="kernel",
        )
        signed = kernel.currency.quote(
            base="GTQ",
            quote_ccy="CNY",
            requester_zid=user.zid,
        )
        assert signed.quote.source.startswith("bridge:USD")
        assert kernel.health().status is HealthStatus.HEALTHY
    finally:
        kernel._db.close()

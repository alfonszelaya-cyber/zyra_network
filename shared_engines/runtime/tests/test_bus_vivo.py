"""VIVA-1: bus vivo de la Red - pruebas."""
from __future__ import annotations

import threading

from shared_engines.events.contracts import EventCatalog
from shared_engines.events.inbox import Inbox
from shared_engines.events.outbox import (
    Outbox, InterAppBridge)
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.common.clocks import FrozenClock


def test_bus_vivo_evento_viaja_solo(tmp_path) -> None:
    cat = EventCatalog()
    cat.register("app.event")
    db = SQLiteAdapter(tmp_path / "bus.db")
    clock = FrozenClock()
    out = Outbox(db, clock)
    out.ensure_schema()
    inbox_b = Inbox(db, clock)
    recibidos = []
    llego = threading.Event()

    def handler(ev):
        recibidos.append(ev.event_id)
        llego.set()

    bridge = InterAppBridge(
        db=db, clock=clock, source=out)
    bridge.subscribe(
        app_id="app-b",
        event_types=("app.event",),
        inbox=inbox_b,
        handler=handler)
    stop = threading.Event()
    hilo = threading.Thread(
        target=lambda: bridge.relay_forever(
            stop=stop, interval_seconds=0.05),
        daemon=True)
    hilo.start()
    ev = cat.build(
        "app.event", aggregate_id="A1",
        payload={"msg": "hola-b"}, clock=clock)
    out.enqueue(ev)
    assert llego.wait(timeout=10), (
        "bus vivo no entrego")
    stop.set()
    hilo.join(timeout=5)
    assert not hilo.is_alive()
    assert recibidos
    print("OK VIVA-1: evento viajo por el bus sin llamada manual")


def test_fx_static_por_defecto(tmp_path, monkeypatch) -> None:
    """VIVA-1: sin ZYRA_FX_LIVE, el kernel es
    determinista (static) - CI estable."""
    monkeypatch.delenv("ZYRA_FX_LIVE", raising=False)
    from shared_engines.runtime.kernel import ZyraKernel
    from shared_engines.verification.signatures import (
        Ed25519Signer)
    db = SQLiteAdapter(tmp_path / "fx.db")
    s, _ = Ed25519Signer.generate()
    k = ZyraKernel(db=db, clock=FrozenClock(),
                   signer=s,
                   config=None) if False else None
    from shared_engines.runtime.config import RuntimeConfig
    k = ZyraKernel(db=db, clock=FrozenClock(),
                   signer=s,
                   config=RuntimeConfig(
                       host="127.0.0.1", port=0,
                       api_token=None))
    q = k.currency.quote(
        base="USD", quote_ccy="EUR",
        requester_zid=k.bootstrap_root().zid)
    assert q.quote.source == "static-table", str(q.quote)
    print("OK VIVA-1: FX determinista sin env (static)")

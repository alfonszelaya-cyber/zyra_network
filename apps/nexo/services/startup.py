
"""Nexo Startup - activacion en el arranque
(NEXO-LIVE-2). attach_live_runtime(result):
extrae defensivamente server/store/client/db/
clock del resultado de _start_nexo (dict u
objeto), construye el runtime conectado
(build_runtime: outbox real + link real + IA
si hay GEMINI_API_KEY) y lo cuelga en el
server, en su handler y en el modulo superapp.
Idempotente y degradacion honesta: sin Red el
runtime vive igual, en buffer."""
from __future__ import annotations

def _pick(obj, names):
    for n in names:
        v = getattr(obj, n, None)
        if v is not None:
            return v
    return None

def attach_live_runtime(result=None):
    """Conecta el runtime vivo tras el arranque
    de NEXO. Nunca lanza: si algo falta, el
    runtime queda honesto (buffer)."""
    from shared_engines.common.clocks import (
        SystemClock)
    from apps.nexo.services.boot import (
        build_runtime)
    server = None
    store = None
    client = None
    db = None
    clock = None
    if isinstance(result, dict):
        server = result.get("server")
        store = result.get("store")
        client = result.get("client")
        db = result.get("db")
        clock = result.get("clock")
    elif result is not None:
        server = _pick(result, ("server",
                                "httpd"))
        store = _pick(result, ("store",))
        client = _pick(result, ("client",
                                "network"))
        db = _pick(result, ("db",))
        clock = _pick(result, ("clock",))
    if store is not None and db is None:
        db = _pick(store, ("db", "_db"))
    if clock is None:
        clock = SystemClock()
    if (server is not None
            and getattr(server,
                        "nexo_runtime",
                        None) is not None):
        return server.nexo_runtime
    rt = build_runtime(db=db, clock=clock,
                       client=client)
    if server is not None:
        try:
            server.nexo_runtime = rt
        except Exception:
            pass
        handler = getattr(server,
                          "RequestHandlerClass",
                          None)
        if handler is not None:
            try:
                handler.nexo_runtime = rt
            except Exception:
                pass
    try:
        import superapp as _sup
        _sup.nexo_runtime = rt
    except Exception:
        pass
    return rt

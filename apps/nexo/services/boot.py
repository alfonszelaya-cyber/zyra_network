
"""Nexo Boot - activacion de NEXO en vivo
(NEXO-LIVE). RedEventMapper: introspecciona la
clase Event REAL de la Red y llena TODOS sus
campos (alias primero, defaults por tipo para
requeridos). RedOutboxAdapter: puente bus ->
Outbox real. Degradacion honesta siempre."""
from __future__ import annotations
import importlib as _imp
import inspect as _inspect
import os as _os

def _find_red_event_cls():
    for modpath in ("shared_engines.events"
                    ".contracts",
                    "shared_engines.events"):
        try:
            m = _imp.import_module(modpath)
        except Exception:
            continue
        cls = getattr(m, "Event", None)
        if cls is not None:
            return cls
    return None

def _fields_of(cls):
    """Lista de (nombre, requerido, anotacion)."""
    if cls is None:
        return []
    try:
        import dataclasses
        out = []
        for f in dataclasses.fields(cls):
            req = (f.default
                   is dataclasses.MISSING
                   and f.default_factory
                   is dataclasses.MISSING)
            out.append((f.name, req,
                        str(f.type)))
        return out
    except Exception:
        pass
    try:
        sig = _inspect.signature(
            cls.__init__)
        out = []
        for name, prm in (sig.parameters
                          .items()):
            if name == "self":
                continue
            req = (prm.default
                   is _inspect.Parameter
                   .empty)
            ann = ("" if prm.annotation
                   is _inspect.Parameter
                   .empty
                   else str(prm.annotation))
            out.append((name, req, ann))
        return out
    except Exception:
        return []

class RedEventMapper:
    """dict NEXO_* -> Event real de la Red."""

    ALIASES = {
        "event_id": ("event_id", "id"),
        "event": ("type", "event_type",
                  "kind", "event", "name"),
        "source": ("source",),
        "payload": ("payload", "data"),
        "occurred_at": ("occurred_at",
                        "created_at",
                        "ts", "at"),
        "version": ("version",),
        "company_id": ("company_id",),
    }

    def __init__(self):
        self._cls = _find_red_event_cls()
        self._fields = _fields_of(self._cls)

    @property
    def available(self) -> bool:
        return (self._cls is not None
                and bool(self._fields))

    @property
    def event_cls(self):
        return self._cls

    def _default_for(self, ann):
        a = (ann or "").lower()
        if ("float" in a or "int" in a
                or "real" in a):
            return 0
        if ("dict" in a or "mapping"
                in a):
            return {}
        if ("list" in a or "tuple"
                in a or "sequence" in a):
            return []
        if "bool" in a:
            return False
        return ""

    def _mapped(self, d):
        kwargs = {}
        for fname, _req, _ann in (
                self._fields):
            opts = self.ALIASES.get(
                fname, (fname,))
            for o in opts:
                if (o in d
                        and d[o] is not None):
                    kwargs[fname] = d[o]
                    break
        return kwargs

    def build(self, d):
        if not self.available:
            return None
        kwargs = self._mapped(d)
        for fname, req, ann in self._fields:
            if fname not in kwargs and req:
                kwargs[fname] = (
                    self._default_for(ann))
        try:
            return self._cls(**kwargs)
        except Exception:
            pass
        minimal = self._mapped(d)
        names = [f[0] for f in self._fields]
        for k, v in (("source", "nexo"),
                     ("version", "1.0")):
            if k in names and k not in (
                    minimal):
                minimal[k] = v
        try:
            return self._cls(**minimal)
        except Exception:
            return None

class RedOutboxAdapter:
    """Puente bus NEXO -> Outbox real."""

    def __init__(self, outbox=None,
                 mapper=None):
        self._outbox = outbox
        self._mapper = (mapper
                        if mapper is not None
                        else RedEventMapper())

    @property
    def connected(self) -> bool:
        return (self._outbox is not None
                and self._mapper.available)

    @property
    def outbox(self):
        return self._outbox

    def append(self, event_dict) -> bool:
        if not self.connected:
            return False
        ev = self._mapper.build(event_dict)
        if ev is None:
            return False
        for name in ("enqueue", "append",
                     "publish", "put", "add"):
            m = getattr(self._outbox, name,
                        None)
            if callable(m):
                try:
                    m(ev)
                    return True
                except TypeError:
                    continue
                except Exception:
                    return False
        return False

def build_outbox(db, clock=None):
    """Outbox real de la Red (multi-firma)."""
    if db is None:
        return None
    try:
        from shared_engines.events.outbox import (
            Outbox)
    except Exception:
        return None
    factories = []
    if clock is not None:
        factories.append(
            lambda: Outbox(db, clock))
        factories.append(
            lambda: Outbox(db=db,
                           clock=clock))
    factories.append(lambda: Outbox(db))
    factories.append(lambda: Outbox(db=db))
    for factory in factories:
        try:
            ob = factory()
        except Exception:
            continue
        ens = getattr(ob, "ensure_schema",
                      None)
        if callable(ens):
            try:
                ens()
            except Exception:
                pass
        return ob
    return None

class _LinkCredShim:
    """request_financial_credential sobre
    issue_financial_credential de NexoLink."""
    def __init__(self, link):
        self._link = link

    def request_financial_credential(
            self, company_id=None,
            payload=None, **kw):
        try:
            ok, data, err = (self._link.
                issue_financial_credential(
                    subject_zid=str(
                        company_id or ""),
                    issuer_zid=str(
                        company_id or ""),
                    title=("Credencial"
                           " financiera"
                           " NEXO"),
                    detail=str(payload
                               or "")))
            return {"ok": bool(ok),
                    "data": data,
                    "error": err}
        except Exception as e:
            return {"ok": False,
                    "error": str(e)[:200]}

def build_ai_chain():
    """AIChain si hay GEMINI_API_KEY."""
    if not _os.environ.get("GEMINI_API_KEY"):
        return None
    try:
        from shared_engines.ai.providers import (
            AIChain)
        return AIChain()
    except Exception:
        return None

def build_runtime(db=None, clock=None,
                  client=None,
                  ai_chain=None):
    """Runtime NEXO conectado; verification y
    outbox_adapter SIEMPRE existen (honestos)."""
    from apps.nexo.services.runtime import (
        NexoRuntime)
    from apps.nexo.services.transversal.verification.verification_gateway import (
        NexoVerificationGateway)
    outbox = build_outbox(db, clock)
    adapter = (RedOutboxAdapter(outbox=outbox)
               if outbox is not None
               else None)
    rt = NexoRuntime(db=db, clock=clock,
                     outbox=adapter,
                     ai_chain=(ai_chain
                               if ai_chain
                               is not None
                               else
                               build_ai_chain()))
    rt.verification = NexoVerificationGateway(
        link=None)
    rt.link = None
    rt.outbox_adapter = adapter
    if client is not None:
        try:
            from apps.nexo.services.nexo_link import (
                NexoLink)
            link = NexoLink(client)
        except Exception:
            link = None
        if link is not None:
            rt.link = link
            rt.verification = (
                NexoVerificationGateway(
                    link=_LinkCredShim(
                        link)))
    return rt

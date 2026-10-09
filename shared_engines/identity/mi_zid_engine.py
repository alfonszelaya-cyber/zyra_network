"""MI ZID Engine (ID-8) - vista agregada de TODO lo
que la Red sabe de un ZID. Compone los engines
existentes (regla 69)."""
from __future__ import annotations
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database


class MiZidEngine:
    """Vista agregada MI ZID (ID-8)."""

    def __init__(self, db: Database, clock: Clock,
                 identity_engine=None,
                 guardian_engine=None,
                 minor_biometrics_engine=None,
                 representation_engine=None):
        self._db = db
        self._clock = clock
        self._ids = identity_engine
        self._guardians = guardian_engine
        self._minor_bio = minor_biometrics_engine
        self._rep = representation_engine

    def portfolio(self, zid):
        if not str(zid).strip():
            raise ValueError("zid requerido")
        out = {"zid": str(zid),
               "identity": None,
               "guardians": [],
               "minors": [],
               "biometrics_phase": None,
               "representations": []}
        if self._ids is not None:
            try:
                ident = self._ids.get_identity(
                    str(zid))
                if ident is not None:
                    out["identity"] = {
                        "status": ident.status
                        .value,
                        "kind": ident.kind.value,
                        "display_name":
                            ident.display_name}
            except Exception:
                pass
        if self._guardians is not None:
            try:
                out["guardians"] = self \
                    ._guardians.guardians_of(
                    str(zid))
                out["minors"] = self \
                    ._guardians.minors_of(
                    str(zid))
            except Exception:
                pass
        if self._minor_bio is not None:
            try:
                out["biometrics_phase"] = self \
                    ._minor_bio.phase_of(
                    str(zid))["phase"]
            except Exception:
                pass
        if self._rep is not None:
            try:
                out["representations"] = self \
                    ._rep.representations_of(
                    str(zid))
            except Exception:
                pass
        return out

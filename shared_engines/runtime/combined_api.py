"""Combined HTTP surface: core API + capabilities
on ONE port.

MRO note: both parents define _route_get/_route_post,
so CombinedHandler overrides both with a
first-segment dispatcher that sends each group to
its correct parent implementation.
"""
from __future__ import annotations

from http.server import ThreadingHTTPServer
from typing import ClassVar
from urllib.parse import urlparse

from shared_engines.common.errors import (
    EngineError,
)
from shared_engines.runtime.api import (
    ZyraApiHandler,
)
from shared_engines.runtime.capabilities import (
    ZyraCapabilities,
)
from shared_engines.runtime.capabilities_api import (
    CapabilitiesApiHandler,
)
from shared_engines.runtime.capabilities_api import (
    _ApiError,
)
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.runtime.responses import (
    ApiError,
    map_engine_error,
)

CORE_PREFIXES = frozenset(
    {
        "health",
        "verify",
        "identity",
        "verification",
        "tokens",
        "currency",
    }
)

CAPS_GET_PREFIXES = frozenset(
    {
        "trust",
        "profile",
        "history",
        "reputation",
        "certificates",
    }
)

CAPS_POST_PREFIXES = frozenset(
    {
        "apps",
        "profile",
        "trust",
        "history",
        "documents",
        "search",
        "reputation",
        "export",
    }
)


class CombinedHandler(
    ZyraApiHandler, CapabilitiesApiHandler
):
    """One port, two surfaces, shared database."""

    caps: ClassVar[ZyraCapabilities]
    kernel: ClassVar[ZyraKernel]

    def _route(self, method: str) -> None:
        path = urlparse(self.path).path
        segments = [
            s
            for s in path.split("/")
            if s
        ]
        if segments and (
            segments[0] in CORE_PREFIXES
        ):
            ZyraApiHandler._route(
                self, method
            )
            return
        CapabilitiesApiHandler._route(
            self, method
        )

    def _route_get(
        self, s: list[str]
    ) -> None:
        if s and s[0] in CAPS_GET_PREFIXES:
            CapabilitiesApiHandler._route_get(
                self, s
            )
            return
        ZyraApiHandler._route_get(self, s)

    def _route_post(
        self, s: list[str]
    ) -> None:
        if s and (
            s[0] in CAPS_POST_PREFIXES
        ):
            CapabilitiesApiHandler._route_post(
                self, s
            )
            return
        ZyraApiHandler._route_post(
            self, s
        )

    def _dispatch(
        self, method: str
    ) -> None:
        try:
            self._route(method)
        except ApiError as exc:
            self._send_json(
                exc.status,
                self._error_body(exc),
            )
        except _ApiError as exc:
            CapabilitiesApiHandler._error(
                self,
                exc.status,
                exc.code,
                exc.message,
            )
        except PermissionError as exc:
            CapabilitiesApiHandler._error(
                self,
                403,
                "forbidden",
                str(exc),
            )
        except EngineError as exc:
            mapped = map_engine_error(exc)
            self._send_json(
                mapped.status,
                self._error_body(mapped),
            )
        except ValueError as exc:
            CapabilitiesApiHandler._error(
                self,
                400,
                "invalid_request",
                str(exc),
            )
        except Exception:
            CapabilitiesApiHandler._error(
                self,
                500,
                "internal_error",
                "internal error",
            )


def serve_combined(
    kernel: ZyraKernel,
    caps: ZyraCapabilities,
    *,
    host: str,
    port: int,
) -> ThreadingHTTPServer:
    """Bind both surfaces to one server."""
    CombinedHandler.kernel = kernel
    CombinedHandler.caps = caps
    return ThreadingHTTPServer(
        (host, port), CombinedHandler
    )

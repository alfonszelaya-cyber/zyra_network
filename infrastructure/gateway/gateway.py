"""
Protocol-neutral request gateway.

Authentication, authorization and transport are intentionally kept
outside this routing primitive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Callable, Mapping


@dataclass(frozen=True, slots=True)
class GatewayRequest:
    method: str
    path: str
    headers: Mapping[str, str] = field(
        default_factory=dict
    )
    body: bytes = b""


@dataclass(frozen=True, slots=True)
class GatewayResponse:
    status_code: int
    headers: Mapping[str, str] = field(
        default_factory=dict
    )
    body: bytes = b""


@dataclass(frozen=True, slots=True)
class Route:
    method: str
    path: str
    handler: Callable[
        [GatewayRequest],
        GatewayResponse,
    ]


class Gateway:
    """Thread-safe exact-match request gateway."""

    def __init__(self) -> None:
        self._routes: dict[
            tuple[str, str],
            Route,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        method: str,
        path: str,
        handler: Callable[
            [GatewayRequest],
            GatewayResponse,
        ],
    ) -> None:
        method = method.strip().upper()

        if not method:
            raise ValueError(
                "method is required"
            )

        if not path.startswith("/"):
            raise ValueError(
                "path must start with '/'"
            )

        if not callable(handler):
            raise TypeError(
                "handler must be callable"
            )

        key = (
            method,
            path,
        )

        with self._lock:
            if key in self._routes:
                raise ValueError(
                    f"route already registered: "
                    f"{method} {path}"
                )

            self._routes[key] = Route(
                method=method,
                path=path,
                handler=handler,
            )

    def dispatch(
        self,
        request: GatewayRequest,
    ) -> GatewayResponse:
        key = (
            request.method.upper(),
            request.path,
        )

        with self._lock:
            route = self._routes.get(
                key
            )

        if route is None:
            return GatewayResponse(
                status_code=404,
                body=(
                    b'{"error":"route_not_found"}'
                ),
            )

        try:
            return route.handler(
                request
            )

        except Exception:
            return GatewayResponse(
                status_code=500,
                body=(
                    b'{"error":'
                    b'"internal_gateway_error"}'
                ),
            )


__all__ = [
    "Gateway",
    "GatewayRequest",
    "GatewayResponse",
    "Route",
]

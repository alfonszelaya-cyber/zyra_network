from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class GatewayRoute:
    path: str
    handler: Callable
    methods: frozenset[str]

    def __post_init__(self) -> None:
        if not self.path.startswith("/"):
            raise ValueError("Gateway path must start with '/'")
        if not callable(self.handler):
            raise TypeError("Gateway handler must be callable")
        if not self.methods:
            raise ValueError("Gateway route requires a method")


class ProtocolGateway:
    """Protocol boundary responsible for dispatching registered routes."""

    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], GatewayRoute] = {}

    def register(
        self,
        path: str,
        handler: Callable,
        methods: set[str] | frozenset[str],
    ) -> None:
        normalized_methods = frozenset(
            method.strip().upper()
            for method in methods
            if method.strip()
        )

        route = GatewayRoute(
            path=path.strip(),
            handler=handler,
            methods=normalized_methods,
        )

        for method in normalized_methods:
            key = (method, route.path)

            if key in self._routes:
                raise ValueError(f"Route already exists: {key}")

            self._routes[key] = route

    def dispatch(
        self,
        method: str,
        path: str,
        *args,
        **kwargs,
    ):
        key = (method.strip().upper(), path.strip())

        try:
            route = self._routes[key]
        except KeyError as exc:
            raise LookupError(f"Route not found: {key}") from exc

        return route.handler(*args, **kwargs)


__all__ = ["GatewayRoute", "ProtocolGateway"]

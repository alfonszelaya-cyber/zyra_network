from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class Route:
    source: str
    destination: str
    protocol: str
    priority: int = 100
    metadata: dict[str, str] | None = None

    def __post_init__(self) -> None:
        source = self.source.strip()
        destination = self.destination.strip()
        protocol = self.protocol.strip()

        if not source:
            raise ValueError(
                "Route source cannot be empty"
            )

        if not destination:
            raise ValueError(
                "Route destination cannot be empty"
            )

        if not protocol:
            raise ValueError(
                "Route protocol cannot be empty"
            )

        if self.priority < 0:
            raise ValueError(
                "Route priority cannot be negative"
            )

        object.__setattr__(
            self,
            "source",
            source,
        )

        object.__setattr__(
            self,
            "destination",
            destination,
        )

        object.__setattr__(
            self,
            "protocol",
            protocol,
        )

        object.__setattr__(
            self,
            "metadata",
            dict(self.metadata or {}),
        )


class RouteTable:

    def __init__(self) -> None:
        self._routes: dict[
            tuple[str, str, str],
            Route,
        ] = {}

        self._lock = RLock()

    def add(self, route: Route) -> None:
        key = (
            route.source,
            route.destination,
            route.protocol,
        )

        with self._lock:
            if key in self._routes:
                raise ValueError(
                    f"Route already exists: {key}"
                )

            self._routes[key] = route

    def remove(
        self,
        source: str,
        destination: str,
        protocol: str,
    ) -> bool:

        key = (
            source.strip(),
            destination.strip(),
            protocol.strip(),
        )

        with self._lock:
            return (
                self._routes.pop(
                    key,
                    None,
                )
                is not None
            )

    def resolve(
        self,
        source: str,
        destination: str,
        protocol: str,
    ) -> Route:

        key = (
            source.strip(),
            destination.strip(),
            protocol.strip(),
        )

        with self._lock:
            try:
                return self._routes[key]
            except KeyError as exc:
                raise LookupError(
                    f"Route not found: {key}"
                ) from exc

    def candidates(
        self,
        source: str,
        destination: str,
    ) -> tuple[Route, ...]:

        source = source.strip()
        destination = destination.strip()

        with self._lock:
            matches = [
                route
                for route in self._routes.values()
                if route.source == source
                and route.destination == destination
            ]

        return tuple(
            sorted(
                matches,
                key=lambda route: (
                    route.priority,
                    route.protocol,
                ),
            )
        )

    def list(self) -> tuple[Route, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._routes.values(),
                    key=lambda route: (
                        route.priority,
                        route.source,
                        route.destination,
                        route.protocol,
                    ),
                )
            )


class Router:

    def __init__(
        self,
        table: RouteTable | None = None,
    ) -> None:

        self.table = table or RouteTable()

    def route(
        self,
        source: str,
        destination: str,
        protocol: str,
    ) -> Route:

        return self.table.resolve(
            source,
            destination,
            protocol,
        )


__all__ = [
    "Route",
    "RouteTable",
    "Router",
]

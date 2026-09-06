"""
Production routing primitives for ZYRA Network.

The routing layer provides:
    - immutable route definitions
    - route policy
    - route tables
    - deterministic route selection
    - route health filtering

It deliberately does not implement:
    - transport I/O
    - consensus
    - persistence
    - application authorization
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Mapping


class RoutePolicy(str, Enum):
    DIRECT = "direct"
    LOWEST_COST = "lowest_cost"
    LOWEST_LATENCY = "lowest_latency"
    HIGHEST_CAPACITY = "highest_capacity"
    WEIGHTED = "weighted"


@dataclass(frozen=True, slots=True)
class Route:
    destination: str
    next_hop: str
    cost: float = 1.0
    latency_ms: float = 0.0
    capacity_bps: int = 1
    weight: int = 1
    healthy: bool = True
    metadata: Mapping[str, str] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        destination = self.destination.strip()
        next_hop = self.next_hop.strip()

        if not destination:
            raise ValueError(
                "route destination cannot be empty"
            )

        if not next_hop:
            raise ValueError(
                "route next_hop cannot be empty"
            )

        if self.cost < 0:
            raise ValueError(
                "route cost cannot be negative"
            )

        if self.latency_ms < 0:
            raise ValueError(
                "route latency cannot be negative"
            )

        if self.capacity_bps <= 0:
            raise ValueError(
                "route capacity must be positive"
            )

        if self.weight <= 0:
            raise ValueError(
                "route weight must be positive"
            )

        object.__setattr__(
            self,
            "destination",
            destination,
        )

        object.__setattr__(
            self,
            "next_hop",
            next_hop,
        )

        object.__setattr__(
            self,
            "metadata",
            dict(self.metadata),
        )


@dataclass(frozen=True, slots=True)
class RouteDecision:
    destination: str
    next_hop: str
    policy: RoutePolicy
    candidates: int


class RouteTable:
    """Thread-safe route table."""

    def __init__(self) -> None:
        self._routes: dict[
            str,
            dict[str, Route],
        ] = {}

        self._lock = RLock()

    def add(
        self,
        route: Route,
    ) -> None:
        if not isinstance(
            route,
            Route,
        ):
            raise TypeError(
                "route must be Route"
            )

        with self._lock:
            destination = route.destination

            bucket = self._routes.setdefault(
                destination,
                {},
            )

            if route.next_hop in bucket:
                raise ValueError(
                    "route already exists: "
                    f"{destination} -> "
                    f"{route.next_hop}"
                )

            bucket[
                route.next_hop
            ] = route

    def replace(
        self,
        route: Route,
    ) -> None:
        if not isinstance(
            route,
            Route,
        ):
            raise TypeError(
                "route must be Route"
            )

        with self._lock:
            self._routes.setdefault(
                route.destination,
                {},
            )[
                route.next_hop
            ] = route

    def remove(
        self,
        destination: str,
        next_hop: str,
    ) -> bool:
        destination = destination.strip()
        next_hop = next_hop.strip()

        with self._lock:
            bucket = self._routes.get(
                destination
            )

            if bucket is None:
                return False

            removed = (
                bucket.pop(
                    next_hop,
                    None,
                )
                is not None
            )

            if not bucket:
                self._routes.pop(
                    destination,
                    None,
                )

            return removed

    def routes(
        self,
        destination: str,
        *,
        healthy_only: bool = True,
    ) -> tuple[Route, ...]:

        destination = destination.strip()

        with self._lock:
            bucket = self._routes.get(
                destination,
                {},
            )

            values = tuple(
                route
                for route in bucket.values()
                if (
                    not healthy_only
                    or route.healthy
                )
            )

            return tuple(
                sorted(
                    values,
                    key=lambda item: (
                        item.cost,
                        item.latency_ms,
                        item.next_hop,
                    ),
                )
            )

    def set_health(
        self,
        destination: str,
        next_hop: str,
        healthy: bool,
    ) -> Route:

        destination = destination.strip()
        next_hop = next_hop.strip()

        with self._lock:
            bucket = self._routes.get(
                destination
            )

            if bucket is None:
                raise LookupError(
                    "destination not found: "
                    f"{destination}"
                )

            route = bucket.get(
                next_hop
            )

            if route is None:
                raise LookupError(
                    "next hop not found: "
                    f"{next_hop}"
                )

            updated = Route(
                destination=route.destination,
                next_hop=route.next_hop,
                cost=route.cost,
                latency_ms=route.latency_ms,
                capacity_bps=route.capacity_bps,
                weight=route.weight,
                healthy=healthy,
                metadata=route.metadata,
            )

            bucket[next_hop] = updated

            return updated

    def destinations(
        self,
    ) -> tuple[str, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._routes
                )
            )


class Router:
    """
    Deterministic route selector.

    Selection is stateless and therefore safe to use concurrently.
    """

    def __init__(
        self,
        table: RouteTable,
    ) -> None:
        if not isinstance(
            table,
            RouteTable,
        ):
            raise TypeError(
                "table must be RouteTable"
            )

        self._table = table

    def select(
        self,
        destination: str,
        *,
        policy: RoutePolicy = (
            RoutePolicy.LOWEST_COST
        ),
    ) -> RouteDecision:

        if not isinstance(
            policy,
            RoutePolicy,
        ):
            raise TypeError(
                "policy must be RoutePolicy"
            )

        candidates = self._table.routes(
            destination,
            healthy_only=True,
        )

        if not candidates:
            raise LookupError(
                "no healthy route for destination: "
                f"{destination}"
            )

        if policy is RoutePolicy.DIRECT:
            selected = min(
                candidates,
                key=lambda item: (
                    0
                    if item.next_hop
                    == item.destination
                    else 1,
                    item.cost,
                    item.next_hop,
                ),
            )

        elif policy is RoutePolicy.LOWEST_LATENCY:
            selected = min(
                candidates,
                key=lambda item: (
                    item.latency_ms,
                    item.cost,
                    item.next_hop,
                ),
            )

        elif policy is RoutePolicy.HIGHEST_CAPACITY:
            selected = max(
                candidates,
                key=lambda item: (
                    item.capacity_bps,
                    -item.cost,
                    item.next_hop,
                ),
            )

        elif policy is RoutePolicy.WEIGHTED:
            selected = max(
                candidates,
                key=lambda item: (
                    item.weight,
                    -item.cost,
                    item.next_hop,
                ),
            )

        else:
            selected = min(
                candidates,
                key=lambda item: (
                    item.cost,
                    item.latency_ms,
                    item.next_hop,
                ),
            )

        return RouteDecision(
            destination=selected.destination,
            next_hop=selected.next_hop,
            policy=policy,
            candidates=len(candidates),
        )


__all__ = [
    "RoutePolicy",
    "Route",
    "RouteDecision",
    "RouteTable",
    "Router",
]

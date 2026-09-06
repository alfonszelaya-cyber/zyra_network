"""
ZYRA Network routing layer.

Routing consumes topology and service information but does not
own transport, consensus or application business logic.
"""

from .router import (
    Route,
    RouteDecision,
    RoutePolicy,
    RouteTable,
    Router,
)

__all__ = [
    "Route",
    "RouteDecision",
    "RoutePolicy",
    "RouteTable",
    "Router",
]

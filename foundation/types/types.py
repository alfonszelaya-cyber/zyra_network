from __future__ import annotations

from typing import NewType, TypeAlias

NodeId = NewType("NodeId", str)
ComponentId = NewType("ComponentId", str)
CorrelationId = NewType("CorrelationId", str)
RegistryId = NewType("RegistryId", str)
EventName = NewType("EventName", str)

JSONPrimitive: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]

__all__ = [
    "NodeId",
    "ComponentId",
    "CorrelationId",
    "RegistryId",
    "EventName",
    "JSONPrimitive",
    "JSONValue",
]

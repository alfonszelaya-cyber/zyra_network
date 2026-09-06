from __future__ import annotations

from typing import NewType, TypeAlias


EntityId = NewType("EntityId", str)
NodeId = NewType("NodeId", str)
TenantId = NewType("TenantId", str)
PrincipalId = NewType("PrincipalId", str)
RequestId = NewType("RequestId", str)
CorrelationId = NewType("CorrelationId", str)
EventId = NewType("EventId", str)
SessionId = NewType("SessionId", str)

JSONPrimitive: TypeAlias = (
    str | int | float | bool | None
)

JSONValue: TypeAlias = (
    JSONPrimitive
    | list["JSONValue"]
    | dict[str, "JSONValue"]
)

Headers: TypeAlias = dict[str, str]
Attributes: TypeAlias = dict[str, JSONValue]

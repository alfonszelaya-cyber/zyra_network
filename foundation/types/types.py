from __future__ import annotations

from typing import (
    Literal,
    NewType,
    TypeAlias,
)


EntityId = NewType(
    "EntityId",
    str,
)

NodeId = NewType(
    "NodeId",
    str,
)

TenantId = NewType(
    "TenantId",
    str,
)

PrincipalId = NewType(
    "PrincipalId",
    str,
)

RequestId = NewType(
    "RequestId",
    str,
)

CorrelationId = NewType(
    "CorrelationId",
    str,
)

CausationId = NewType(
    "CausationId",
    str,
)

EventId = NewType(
    "EventId",
    str,
)

SessionId = NewType(
    "SessionId",
    str,
)

CredentialId = NewType(
    "CredentialId",
    str,
)

CertificateId = NewType(
    "CertificateId",
    str,
)

ShipmentId = NewType(
    "ShipmentId",
    str,
)

LocationId = NewType(
    "LocationId",
    str,
)


JSONPrimitive: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
)

JSONValue: TypeAlias = (
    JSONPrimitive
    | list["JSONValue"]
    | dict[str, "JSONValue"]
)

JSONObject: TypeAlias = dict[
    str,
    JSONValue,
]

Headers: TypeAlias = dict[str, str]

Attributes: TypeAlias = dict[
    str,
    JSONValue,
]

EnvironmentName: TypeAlias = Literal[
    "development",
    "testing",
    "staging",
    "production",
]

UUIDString: TypeAlias = str
ISO8601String: TypeAlias = str
SHA256Digest: TypeAlias = str
URLString: TypeAlias = str

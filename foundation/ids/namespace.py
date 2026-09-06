from __future__ import annotations

from enum import StrEnum


class Namespace(StrEnum):
    """
    Reserved universal namespaces for ZYRA identifiers.

    Applications may use their own namespace without changing
    the identifier implementation.
    """

    NETWORK = "network"
    NODE = "node"
    PERSON = "person"
    COMPANY = "company"
    GOVERNMENT = "government"
    AI = "ai"
    DEVICE = "device"
    DOCUMENT = "document"
    CONTRACT = "contract"
    VEHICLE = "vehicle"
    PROPERTY = "property"
    ASSET = "asset"
    TRANSACTION = "transaction"
    EVENT = "event"
    SESSION = "session"
    CREDENTIAL = "credential"
    CERTIFICATE = "certificate"
    SHIPMENT = "shipment"
    LOCATION = "location"
    WORKFLOW = "workflow"

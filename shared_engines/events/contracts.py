"""Versioned event contracts and the central catalog.

Every event carries: event_id, event_type, aggregate_id,
schema_version, envelope_version, timestamp, payload and a
stable fingerprint. Evolving an event means registering a new
schema_version, never mutating the old one.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import (
    ConfigurationError,
    UnsupportedVersionError,
    ValidationError,
)
from shared_engines.common.identifiers import new_id, stable_hash
from shared_engines.common.serialization import canonical_json_dumps

EVENT_ENVELOPE_VERSION = 1
PayloadValidator = Callable[[Mapping[str, object]], None]


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: str
    aggregate_id: str
    schema_version: int
    envelope_version: int
    timestamp: float
    payload: Mapping[str, object]
    fingerprint: str


def _default_validator(payload: Mapping[str, object]) -> None:
    if not isinstance(payload, dict):
        raise ValidationError("event payload must be a mapping")


class EventCatalog:
    """Central registry: type -> version -> validator.

    Registering the same type and version twice is an
    idempotent no-op so several engines can share one catalog.
    """

    def __init__(self) -> None:
        self._schemas: dict[str, dict[int, PayloadValidator]] = {}

    def register(
        self,
        event_type: str,
        *,
        schema_version: int = 1,
        validator: PayloadValidator | None = None,
    ) -> None:
        if not event_type:
            raise ConfigurationError("event_type must be non-empty")
        if schema_version <= 0:
            raise ConfigurationError("schema_version must be positive")
        validators = self._schemas.setdefault(event_type, {})
        if schema_version in validators:
            return
        validators[schema_version] = validator or _default_validator

    def build(
        self,
        event_type: str,
        *,
        aggregate_id: str,
        payload: Mapping[str, object],
        clock: Clock,
        schema_version: int | None = None,
    ) -> Event:
        versions = self._schemas.get(event_type)
        if not versions:
            raise ValidationError(
                f"event type not registered: {event_type}"
            )
        version = (
            schema_version if schema_version is not None else max(versions)
        )
        validator = versions.get(version)
        if validator is None:
            raise UnsupportedVersionError(
                f"unsupported version {version} for {event_type}"
            )
        validator(payload)
        fingerprint = stable_hash(
            event_type,
            aggregate_id,
            str(version),
            canonical_json_dumps(dict(payload)),
        )
        return Event(
            event_id=new_id(),
            event_type=event_type,
            aggregate_id=aggregate_id,
            schema_version=version,
            envelope_version=EVENT_ENVELOPE_VERSION,
            timestamp=clock.now(),
            payload=dict(payload),
            fingerprint=fingerprint,
        )

    @property
    def registered_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._schemas))

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


LOGGER = logging.getLogger("zyra.observability")


# ============================================================
# ERRORS
# ============================================================

class ObservabilityError(RuntimeError):
    """Base exception for the ZYRA observability subsystem."""


class ObservationError(ObservabilityError):
    """Backward-compatible public exception name."""


class ValidationError(ObservabilityError):
    """Invalid observability contract or configuration."""


class LifecycleError(ObservabilityError):
    """Invalid service lifecycle transition."""


class StorageError(ObservabilityError):
    """Durability or storage failure."""


# ============================================================
# ENUMS
# ============================================================

class Severity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricKind(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AlertState(str, Enum):
    INACTIVE = "inactive"
    FIRING = "firing"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class IncidentState(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class LifecycleState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"


# ============================================================
# TIME / IDS / VALIDATION
# ============================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime | None = None) -> str:
    return (value or utc_now()).astimezone(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(raw).hexdigest()


def validate_name(value: str, field_name: str = "name") -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string")

    value = value.strip()

    if not value:
        raise ValidationError(f"{field_name} cannot be empty")

    if len(value) > 256:
        raise ValidationError(
            f"{field_name} exceeds maximum length"
        )

    return value


def sanitize_labels(
    labels: Mapping[str, Any] | None,
    *,
    max_items: int = 32,
    max_length: int = 128,
) -> dict[str, str]:

    if not labels:
        return {}

    result: dict[str, str] = {}

    for key, value in list(labels.items())[:max_items]:
        safe_key = validate_name(str(key), "label")[:max_length]
        safe_value = str(value)[:max_length]
        result[safe_key] = safe_value

    return result


# ============================================================
# CONTEXT
# ============================================================

@dataclass(frozen=True, slots=True)
class ObservationContext:
    correlation_id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    component: str
    operation: str
    labels: tuple[tuple[str, str], ...]

    @classmethod
    def create(
        cls,
        *,
        component: str,
        operation: str,
        correlation_id: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        labels: Mapping[str, Any] | None = None,
    ) -> "ObservationContext":

        return cls(
            correlation_id=correlation_id or new_id("corr"),
            trace_id=trace_id or new_id("trace"),
            span_id=new_id("span"),
            parent_span_id=parent_span_id,
            component=validate_name(component, "component"),
            operation=validate_name(operation, "operation"),
            labels=tuple(
                sorted(
                    sanitize_labels(labels).items()
                )
            ),
        )

    def child(self, operation: str) -> "ObservationContext":
        return self.create(
            component=self.component,
            operation=operation,
            correlation_id=self.correlation_id,
            trace_id=self.trace_id,
            parent_span_id=self.span_id,
            labels=dict(self.labels),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "component": self.component,
            "operation": self.operation,
            "labels": dict(self.labels),
        }


# ============================================================
# EVENTS
# ============================================================

@dataclass(frozen=True, slots=True)
class ObservationEvent:
    event_id: str
    timestamp: datetime
    event_type: str
    severity: Severity
    message: str
    context: ObservationContext
    attributes: Mapping[str, Any]

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        severity: Severity,
        message: str,
        context: ObservationContext,
        attributes: Mapping[str, Any] | None = None,
    ) -> "ObservationEvent":

        return cls(
            event_id=new_id("evt"),
            timestamp=utc_now(),
            event_type=validate_name(
                event_type,
                "event_type",
            ),
            severity=severity,
            message=str(message)[:8192],
            context=context,
            attributes=dict(attributes or {}),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": utc_iso(self.timestamp),
            "event_type": self.event_type,
            "severity": self.severity.value,
            "message": self.message,
            "context": self.context.as_dict(),
            "attributes": dict(self.attributes),
        }


# ============================================================
# METRICS
# ============================================================

@dataclass(frozen=True, slots=True)
class MetricSample:
    metric_id: str
    name: str
    kind: MetricKind
    timestamp: datetime
    value: float
    labels: Mapping[str, str]
    unit: str | None = None

    @classmethod
    def create(
        cls,
        *,
        name: str,
        kind: MetricKind,
        value: float,
        labels: Mapping[str, Any] | None = None,
        unit: str | None = None,
    ) -> "MetricSample":

        value = float(value)

        if not math.isfinite(value):
            raise ValidationError(
                "Metric values must be finite."
            )

        return cls(
            metric_id=new_id("metric"),
            name=validate_name(name),
            kind=kind,
            timestamp=utc_now(),
            value=value,
            labels=sanitize_labels(labels),
            unit=unit,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "kind": self.kind.value,
            "timestamp": utc_iso(self.timestamp),
            "value": self.value,
            "labels": dict(self.labels),
            "unit": self.unit,
        }


class MetricRegistry:
    def __init__(
        self,
        *,
        max_samples: int = 250_000,
    ) -> None:

        if max_samples <= 0:
            raise ValidationError(
                "max_samples must be positive"
            )

        self._samples: deque[MetricSample] = deque(
            maxlen=max_samples
        )

        self._counters: dict[
            tuple[str, tuple[tuple[str, str], ...]],
            float,
        ] = {}

        self._gauges: dict[
            tuple[str, tuple[tuple[str, str], ...]],
            float,
        ] = {}

        self._lock = threading.RLock()

    def record(
        self,
        sample: MetricSample,
    ) -> MetricSample:

        key = (
            sample.name,
            tuple(sorted(sample.labels.items())),
        )

        with self._lock:
            self._samples.append(sample)

            if sample.kind is MetricKind.COUNTER:
                self._counters[key] = (
                    self._counters.get(key, 0.0)
                    + sample.value
                )

            elif sample.kind is MetricKind.GAUGE:
                self._gauges[key] = sample.value

        return sample

    def counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Mapping[str, Any] | None = None,
        unit: str | None = None,
    ) -> MetricSample:

        return self.record(
            MetricSample.create(
                name=name,
                kind=MetricKind.COUNTER,
                value=value,
                labels=labels,
                unit=unit,
            )
        )

    def gauge(
        self,
        name: str,
        value: float,
        labels: Mapping[str, Any] | None = None,
        unit: str | None = None,
    ) -> MetricSample:

        return self.record(
            MetricSample.create(
                name=name,
                kind=MetricKind.GAUGE,
                value=value,
                labels=labels,
                unit=unit,
            )
        )

    def query(
        self,
        name: str | None = None,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        labels: Mapping[str, Any] | None = None,
    ) -> list[MetricSample]:

        expected = sanitize_labels(labels)

        with self._lock:
            samples = list(self._samples)

        result: list[MetricSample] = []

        for sample in samples:
            if name is not None and sample.name != name:
                continue

            if start is not None and sample.timestamp < start:
                continue

            if end is not None and sample.timestamp > end:
                continue

            if expected:
                if dict(sample.labels) != expected:
                    continue

            result.append(sample)

        return result

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "sample_count": len(self._samples),
                "counter_count": len(self._counters),
                "gauge_count": len(self._gauges),
            }


# ============================================================
# RETENTION
# ============================================================

@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    max_events: int = 100_000
    max_metrics: int = 250_000
    max_alerts: int = 25_000
    max_incidents: int = 10_000
    max_labels: int = 32

    def __post_init__(self) -> None:
        for name, value in (
            ("max_events", self.max_events),
            ("max_metrics", self.max_metrics),
            ("max_alerts", self.max_alerts),
            ("max_incidents", self.max_incidents),
            ("max_labels", self.max_labels),
        ):
            if value <= 0:
                raise ValidationError(
                    f"{name} must be positive"
                )


# ============================================================
# EVENT BUS
# ============================================================

class EventBus:
    def __init__(
        self,
        *,
        max_events: int = 100_000,
    ) -> None:

        self._events: deque[ObservationEvent] = deque(
            maxlen=max_events
        )

        self._subscribers: dict[
            str,
            list[Callable[[ObservationEvent], None]],
        ] = {}

        self._lock = threading.RLock()

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[ObservationEvent], None],
    ) -> None:

        if not callable(callback):
            raise ValidationError(
                "callback must be callable"
            )

        with self._lock:
            self._subscribers.setdefault(
                event_type,
                [],
            ).append(callback)

    def publish(
        self,
        event: ObservationEvent,
    ) -> None:

        with self._lock:
            self._events.append(event)

            callbacks = list(
                self._subscribers.get(
                    event.event_type,
                    [],
                )
            )

            callbacks.extend(
                self._subscribers.get("*", [])
            )

        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                LOGGER.exception(
                    "Observability subscriber failed"
                )

    def recent(
        self,
        limit: int = 100,
    ) -> list[ObservationEvent]:

        if limit <= 0:
            return []

        with self._lock:
            return list(self._events)[-limit:]


# ============================================================
# HEALTH
# ============================================================

@dataclass(frozen=True, slots=True)
class HealthResult:
    component: str
    state: HealthState
    checked_at: datetime
    latency_ms: float
    message: str
    details: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "state": self.state.value,
            "checked_at": utc_iso(self.checked_at),
            "latency_ms": self.latency_ms,
            "message": self.message,
            "details": dict(self.details),
        }


class HealthRegistry:
    def __init__(self) -> None:
        self._checks: dict[
            str,
            Callable[[], Any],
        ] = {}

        self._lock = threading.RLock()

    def register(
        self,
        component: str,
        check: Callable[[], Any],
    ) -> None:

        component = validate_name(
            component,
            "component",
        )

        if not callable(check):
            raise ValidationError(
                "health check must be callable"
            )

        with self._lock:
            self._checks[component] = check

    def unregister(self, component: str) -> None:
        with self._lock:
            self._checks.pop(component, None)

    def check(
        self,
        component: str,
    ) -> HealthResult:

        with self._lock:
            check = self._checks.get(component)

        if check is None:
            return HealthResult(
                component=component,
                state=HealthState.UNKNOWN,
                checked_at=utc_now(),
                latency_ms=0.0,
                message="No health check registered",
                details={},
            )

        started = time.perf_counter()

        try:
            value = check()

            if isinstance(value, HealthResult):
                return value

            state = (
                HealthState.HEALTHY
                if value is not False
                else HealthState.UNHEALTHY
            )

            return HealthResult(
                component=component,
                state=state,
                checked_at=utc_now(),
                latency_ms=(
                    time.perf_counter() - started
                ) * 1000,
                message="Health check completed",
                details={"result": value},
            )

        except Exception as exc:
            return HealthResult(
                component=component,
                state=HealthState.UNHEALTHY,
                checked_at=utc_now(),
                latency_ms=(
                    time.perf_counter() - started
                ) * 1000,
                message=str(exc)[:2048],
                details={},
            )

    def check_all(self) -> list[HealthResult]:
        with self._lock:
            components = list(self._checks)

        return [
            self.check(component)
            for component in components
        ]


# ============================================================
# ALERTS
# ============================================================

@dataclass(frozen=True, slots=True)
class AlertRule:
    rule_id: str
    name: str
    metric_name: str
    threshold: float
    operator: str = ">"
    severity: Severity = Severity.WARNING
    cooldown_seconds: float = 300.0

    def evaluate(self, value: float) -> bool:
        operators = {
            ">": lambda: value > self.threshold,
            ">=": lambda: value >= self.threshold,
            "<": lambda: value < self.threshold,
            "<=": lambda: value <= self.threshold,
            "==": lambda: value == self.threshold,
            "!=": lambda: value != self.threshold,
        }

        evaluator = operators.get(self.operator)

        if evaluator is None:
            raise ValidationError(
                f"Unsupported operator: {self.operator}"
            )

        return evaluator()


@dataclass
class Alert:
    alert_id: str
    rule_id: str
    fingerprint: str
    state: AlertState
    severity: Severity
    message: str
    value: float
    created_at: datetime
    updated_at: datetime

    def as_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "rule_id": self.rule_id,
            "fingerprint": self.fingerprint,
            "state": self.state.value,
            "severity": self.severity.value,
            "message": self.message,
            "value": self.value,
            "created_at": utc_iso(self.created_at),
            "updated_at": utc_iso(self.updated_at),
        }


class AlertManager:
    def __init__(
        self,
        *,
        max_alerts: int = 25_000,
    ) -> None:

        self._rules: dict[str, AlertRule] = {}
        self._alerts: dict[str, Alert] = {}
        self._max_alerts = max_alerts
        self._lock = threading.RLock()

    def register_rule(
        self,
        rule: AlertRule,
    ) -> None:

        if rule.cooldown_seconds < 0:
            raise ValidationError(
                "cooldown_seconds cannot be negative"
            )

        with self._lock:
            self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> None:
        with self._lock:
            self._rules.pop(rule_id, None)

    def evaluate(
        self,
        sample: MetricSample,
    ) -> list[Alert]:

        now = utc_now()
        results: list[Alert] = []

        with self._lock:
            rules = [
                rule
                for rule in self._rules.values()
                if rule.metric_name == sample.name
            ]

            for rule in rules:
                fingerprint = stable_hash(
                    {
                        "rule_id": rule.rule_id,
                        "metric": sample.name,
                        "labels": dict(sample.labels),
                    }
                )

                alert = self._alerts.get(fingerprint)

                if rule.evaluate(sample.value):
                    if alert is None:
                        alert = Alert(
                            alert_id=new_id("alert"),
                            rule_id=rule.rule_id,
                            fingerprint=fingerprint,
                            state=AlertState.FIRING,
                            severity=rule.severity,
                            message=(
                                f"{sample.name} "
                                f"{rule.operator} "
                                f"{rule.threshold}"
                            ),
                            value=sample.value,
                            created_at=now,
                            updated_at=now,
                        )
                        self._alerts[fingerprint] = alert
                    else:
                        alert.state = AlertState.FIRING
                        alert.value = sample.value
                        alert.updated_at = now

                    results.append(alert)

                elif alert is not None:
                    alert.state = AlertState.RESOLVED
                    alert.value = sample.value
                    alert.updated_at = now
                    results.append(alert)

            while len(self._alerts) > self._max_alerts:
                oldest = min(
                    self._alerts.values(),
                    key=lambda item: item.updated_at,
                )

                self._alerts.pop(
                    oldest.fingerprint,
                    None,
                )

        return results

    def active(self) -> list[Alert]:
        with self._lock:
            return [
                alert
                for alert in self._alerts.values()
                if alert.state in (
                    AlertState.FIRING,
                    AlertState.ACKNOWLEDGED,
                )
            ]

    def all(self) -> list[Alert]:
        with self._lock:
            return list(self._alerts.values())


# ============================================================
# INCIDENTS
# ============================================================

@dataclass
class Incident:
    incident_id: str
    title: str
    severity: Severity
    state: IncidentState
    created_at: datetime
    updated_at: datetime
    alert_ids: set[str] = field(default_factory=set)
    event_ids: set[str] = field(default_factory=set)
    notes: list[str] = field(default_factory=list)

    def attach_alert(
        self,
        alert_id: str,
    ) -> None:

        self.alert_ids.add(alert_id)
        self.updated_at = utc_now()

    def attach_event(
        self,
        event_id: str,
    ) -> None:

        self.event_ids.add(event_id)
        self.updated_at = utc_now()

    def transition(
        self,
        state: IncidentState,
    ) -> None:

        self.state = state
        self.updated_at = utc_now()

    def add_note(
        self,
        note: str,
    ) -> None:

        self.notes.append(str(note)[:8192])
        self.updated_at = utc_now()

    def as_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "severity": self.severity.value,
            "state": self.state.value,
            "created_at": utc_iso(self.created_at),
            "updated_at": utc_iso(self.updated_at),
            "alert_ids": sorted(self.alert_ids),
            "event_ids": sorted(self.event_ids),
            "notes": list(self.notes),
        }


class IncidentManager:
    def __init__(
        self,
        *,
        max_incidents: int = 10_000,
    ) -> None:

        self._incidents: dict[str, Incident] = {}
        self._max_incidents = max_incidents
        self._lock = threading.RLock()

    def create(
        self,
        title: str,
        *,
        severity: Severity = Severity.ERROR,
    ) -> Incident:

        now = utc_now()

        incident = Incident(
            incident_id=new_id("incident"),
            title=validate_name(title, "title"),
            severity=severity,
            state=IncidentState.OPEN,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._incidents[
                incident.incident_id
            ] = incident

            while len(self._incidents) > self._max_incidents:
                oldest = min(
                    self._incidents.values(),
                    key=lambda item: item.updated_at,
                )

                self._incidents.pop(
                    oldest.incident_id,
                    None,
                )

        return incident

    def get(
        self,
        incident_id: str,
    ) -> Incident | None:

        with self._lock:
            return self._incidents.get(incident_id)

    def active(self) -> list[Incident]:
        with self._lock:
            return [
                incident
                for incident in self._incidents.values()
                if incident.state not in (
                    IncidentState.RESOLVED,
                    IncidentState.CLOSED,
                )
            ]

    def all(self) -> list[Incident]:
        with self._lock:
            return list(self._incidents.values())


# ============================================================
# COMPONENT REGISTRY
# ============================================================

class ComponentRegistry:
    def __init__(self) -> None:
        self._components: dict[
            str,
            dict[str, Any],
        ] = {}

        self._lock = threading.RLock()

    def register(
        self,
        name: str,
        *,
        kind: str = "component",
        metadata: Mapping[str, Any] | None = None,
    ) -> None:

        name = validate_name(name)

        with self._lock:
            self._components[name] = {
                "name": name,
                "kind": kind,
                "metadata": dict(metadata or {}),
                "registered_at": utc_iso(),
            }

    def unregister(
        self,
        name: str,
    ) -> None:

        with self._lock:
            self._components.pop(name, None)

    def get(
        self,
        name: str,
    ) -> dict[str, Any] | None:

        with self._lock:
            value = self._components.get(name)

            return dict(value) if value else None

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                dict(value)
                for value in self._components.values()
            ]


# ============================================================
# DURABLE STORAGE
# ============================================================

class ObservationStore:
    """
    Append-only JSON Lines persistence.

    Writes are flushed and optionally fsynced. Recovery is tolerant
    of a truncated final record. Compaction is performed atomically
    through a temporary file replacement.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        max_records: int = 250_000,
        fsync: bool = True,
    ) -> None:

        if max_records <= 0:
            raise ValidationError(
                "max_records must be positive"
            )

        self.path = Path(path)
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.max_records = max_records
        self.fsync = fsync

        self._lock = threading.RLock()
        self._records = 0

        self._recover()

    def _recover(self) -> None:
        if not self.path.exists():
            self._records = 0
            return

        count = 0

        with self.path.open(
            "rb"
        ) as handle:

            for line in handle:
                if line.strip():
                    count += 1

        self._records = count

    def append(
        self,
        record: Mapping[str, Any],
    ) -> None:

        payload = dict(record)
        payload.setdefault(
            "stored_at",
            utc_iso(),
        )

        encoded = (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            + "\n"
        ).encode("utf-8")

        with self._lock:
            if self._records >= self.max_records:
                self._compact_locked()

            try:
                with self.path.open(
                    "ab"
                ) as handle:

                    handle.write(encoded)
                    handle.flush()

                    if self.fsync:
                        os.fsync(
                            handle.fileno()
                        )

                self._records += 1

            except OSError as exc:
                raise StorageError(
                    f"Unable to append observation: {exc}"
                ) from exc

    def read_all(
        self,
    ) -> list[dict[str, Any]]:

        if not self.path.exists():
            return []

        records: list[dict[str, Any]] = []

        with self._lock:
            with self.path.open(
                "r",
                encoding="utf-8",
            ) as handle:

                for line in handle:
                    if not line.strip():
                        continue

                    try:
                        records.append(
                            json.loads(line)
                        )
                    except json.JSONDecodeError:
                        LOGGER.warning(
                            "Ignoring incomplete observation record"
                        )

        return records

    def _compact_locked(self) -> None:
        records = self.read_all()

        keep = max(
            1,
            self.max_records // 2,
        )

        records = records[-keep:]

        temporary = self.path.with_name(
            self.path.name + ".compact"
        )

        try:
            with temporary.open(
                "w",
                encoding="utf-8",
            ) as handle:

                for record in records:
                    handle.write(
                        json.dumps(
                            record,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                            default=str,
                        )
                    )
                    handle.write("\n")

                handle.flush()

                if self.fsync:
                    os.fsync(
                        handle.fileno()
                    )

            temporary.replace(self.path)
            self._records = len(records)

        except OSError as exc:
            try:
                temporary.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            raise StorageError(
                f"Observation compaction failed: {exc}"
            ) from exc

    def count(self) -> int:
        with self._lock:
            return self._records


# ============================================================
# ENGINE
# ============================================================

class ObservationEngine:
    def __init__(
        self,
        *,
        metrics: MetricRegistry,
        events: EventBus,
        alerts: AlertManager,
        health: HealthRegistry,
    ) -> None:

        self.metrics = metrics
        self.events = events
        self.alerts = alerts
        self.health = health

    def record_event(
        self,
        event: ObservationEvent,
    ) -> ObservationEvent:

        self.events.publish(event)
        return event

    def record_metric(
        self,
        sample: MetricSample,
    ) -> list[Alert]:

        self.metrics.record(sample)

        return self.alerts.evaluate(
            sample
        )

    def emit(
        self,
        *,
        event_type: str,
        severity: Severity,
        message: str,
        context: ObservationContext,
        attributes: Mapping[str, Any] | None = None,
    ) -> ObservationEvent:

        return self.record_event(
            ObservationEvent.create(
                event_type=event_type,
                severity=severity,
                message=message,
                context=context,
                attributes=attributes,
            )
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "metrics": self.metrics.snapshot(),
            "events": len(
                self.events.recent(1_000_000)
            ),
            "active_alerts": len(
                self.alerts.active()
            ),
            "health": [
                item.as_dict()
                for item in self.health.check_all()
            ],
        }


# ============================================================
# MANAGER
# ============================================================

class ObservationManager:
    def __init__(
        self,
        *,
        storage_path: str | Path | None = None,
        retention: RetentionPolicy | None = None,
    ) -> None:

        self.retention = (
            retention or RetentionPolicy()
        )

        self.metrics = MetricRegistry(
            max_samples=self.retention.max_metrics
        )

        self.events = EventBus(
            max_events=self.retention.max_events
        )

        self.alerts = AlertManager(
            max_alerts=self.retention.max_alerts
        )

        self.health = HealthRegistry()

        self.incidents = IncidentManager(
            max_incidents=self.retention.max_incidents
        )

        self.registry = ComponentRegistry()

        self.engine = ObservationEngine(
            metrics=self.metrics,
            events=self.events,
            alerts=self.alerts,
            health=self.health,
        )

        self.storage = (
            ObservationStore(
                storage_path,
                max_records=self.retention.max_events,
            )
            if storage_path
            else None
        )

        self._state = LifecycleState.CREATED
        self._lock = threading.RLock()

    @property
    def state(self) -> LifecycleState:
        with self._lock:
            return self._state

    def start(self) -> None:
        with self._lock:
            if self._state is LifecycleState.RUNNING:
                return

            if self._state not in (
                LifecycleState.CREATED,
                LifecycleState.STOPPED,
            ):
                raise LifecycleError(
                    f"Cannot start from "
                    f"{self._state.value}"
                )

            self._state = LifecycleState.RUNNING

    def stop(self) -> None:
        with self._lock:
            if self._state is LifecycleState.STOPPED:
                return

            if self._state not in (
                LifecycleState.RUNNING,
                LifecycleState.STOPPING,
            ):
                self._state = LifecycleState.STOPPED
                return

            self._state = LifecycleState.STOPPING
            self._state = LifecycleState.STOPPED

    def record_event(
        self,
        event: ObservationEvent,
    ) -> ObservationEvent:

        if self.state is not LifecycleState.RUNNING:
            raise LifecycleError(
                "ObservationManager is not running"
            )

        result = self.engine.record_event(
            event
        )

        if self.storage:
            self.storage.append(
                {
                    "type": "event",
                    "payload": result.as_dict(),
                }
            )

        return result

    def record_metric(
        self,
        sample: MetricSample,
    ) -> list[Alert]:

        if self.state is not LifecycleState.RUNNING:
            raise LifecycleError(
                "ObservationManager is not running"
            )

        alerts = self.engine.record_metric(
            sample
        )

        if self.storage:
            self.storage.append(
                {
                    "type": "metric",
                    "payload": sample.as_dict(),
                }
            )

            for alert in alerts:
                self.storage.append(
                    {
                        "type": "alert",
                        "payload": alert.as_dict(),
                    }
                )

        return alerts

    def status(self) -> dict[str, Any]:
        with self._lock:
            state = self._state.value

        return {
            "state": state,
            "components": len(
                self.registry.all()
            ),
            "active_alerts": len(
                self.alerts.active()
            ),
            "active_incidents": len(
                self.incidents.active()
            ),
            "metrics": self.metrics.snapshot(),
            "storage_records": (
                self.storage.count()
                if self.storage
                else 0
            ),
        }


# ============================================================
# PUBLIC API
# ============================================================

class ObservationAPI:
    def __init__(
        self,
        manager: ObservationManager,
    ) -> None:

        self.manager = manager

    def start(self) -> None:
        self.manager.start()

    def stop(self) -> None:
        self.manager.stop()

    def context(
        self,
        component: str,
        operation: str,
        **kwargs: Any,
    ) -> ObservationContext:

        return ObservationContext.create(
            component=component,
            operation=operation,
            **kwargs,
        )

    def event(
        self,
        *,
        context: ObservationContext,
        event_type: str,
        severity: Severity,
        message: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> ObservationEvent:

        event = ObservationEvent.create(
            event_type=event_type,
            severity=severity,
            message=message,
            context=context,
            attributes=attributes,
        )

        return self.manager.record_event(
            event
        )

    def counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Mapping[str, Any] | None = None,
    ) -> MetricSample:

        sample = MetricSample.create(
            name=name,
            kind=MetricKind.COUNTER,
            value=value,
            labels=labels,
        )

        self.manager.record_metric(
            sample
        )

        return sample

    def gauge(
        self,
        name: str,
        value: float,
        labels: Mapping[str, Any] | None = None,
    ) -> MetricSample:

        sample = MetricSample.create(
            name=name,
            kind=MetricKind.GAUGE,
            value=value,
            labels=labels,
        )

        self.manager.record_metric(
            sample
        )

        return sample

    def status(self) -> dict[str, Any]:
        return self.manager.status()


__all__ = [
    "Alert",
    "AlertManager",
    "AlertRule",
    "AlertState",
    "ComponentRegistry",
    "EventBus",
    "HealthRegistry",
    "HealthResult",
    "HealthState",
    "Incident",
    "IncidentManager",
    "IncidentState",
    "LifecycleError",
    "LifecycleState",
    "MetricKind",
    "MetricRegistry",
    "MetricSample",
    "ObservationAPI",
    "ObservationContext",
    "ObservationEngine",
    "ObservationError",
    "ObservationEvent",
    "ObservationManager",
    "ObservationStore",
    "ObservabilityError",
    "RetentionPolicy",
    "Severity",
    "StorageError",
    "ValidationError",
    "new_id",
    "stable_hash",
    "utc_iso",
    "utc_now",
]

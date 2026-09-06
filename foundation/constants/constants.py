from __future__ import annotations

from enum import StrEnum


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class ComponentStatus(StrEnum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class OperationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


NETWORK_NAME = "ZYRA_NETWORK"
NETWORK_PROTOCOL_VERSION = 1
NETWORK_API_VERSION = "v1"

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000

DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 30.0

DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 5.0
DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 15.0

MAX_IDENTIFIER_LENGTH = 256
MAX_METADATA_KEYS = 256
MAX_METADATA_VALUE_LENGTH = 4096

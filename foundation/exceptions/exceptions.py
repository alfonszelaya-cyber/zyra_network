from __future__ import annotations


class ZyraError(Exception):
    """Base exception for all controlled ZYRA failures."""

    code = "ZYRA_ERROR"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }


class ConfigurationError(ZyraError):
    code = "CONFIGURATION_ERROR"


class ValidationError(ZyraError):
    code = "VALIDATION_ERROR"


class AuthenticationError(ZyraError):
    code = "AUTHENTICATION_ERROR"


class AuthorizationError(ZyraError):
    code = "AUTHORIZATION_ERROR"


class NotFoundError(ZyraError):
    code = "NOT_FOUND"


class ConflictError(ZyraError):
    code = "CONFLICT"


class LifecycleError(ZyraError):
    code = "LIFECYCLE_ERROR"


class NetworkError(ZyraError):
    code = "NETWORK_ERROR"


class TransportError(NetworkError):
    code = "TRANSPORT_ERROR"


class TimeoutError(NetworkError):
    code = "TIMEOUT"


class StorageError(ZyraError):
    code = "STORAGE_ERROR"


class IntegrityError(ZyraError):
    code = "INTEGRITY_ERROR"


class SecurityError(ZyraError):
    code = "SECURITY_ERROR"


class DependencyError(ZyraError):
    code = "DEPENDENCY_ERROR"


class RateLimitError(ZyraError):
    code = "RATE_LIMIT"


class ServiceUnavailableError(ZyraError):
    code = "SERVICE_UNAVAILABLE"

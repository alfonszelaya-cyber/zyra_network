from __future__ import annotations

from typing import Any


class ZyraError(Exception):
    """
    Base exception for controlled ZYRA failures.

    Every Network exception has a stable machine-readable code
    and optional structured diagnostic details.
    """

    code = "ZYRA_ERROR"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)

        if not isinstance(message, str) or not message.strip():
            raise ValueError(
                "Exception message cannot be empty"
            )

        self.message = message
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
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


class IdentityError(ZyraError):
    code = "IDENTITY_ERROR"


class CredentialError(ZyraError):
    code = "CREDENTIAL_ERROR"


class CertificateError(ZyraError):
    code = "CERTIFICATE_ERROR"


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


class RoutingError(NetworkError):
    code = "ROUTING_ERROR"


class DiscoveryError(NetworkError):
    code = "DISCOVERY_ERROR"


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


class ConsensusError(NetworkError):
    code = "CONSENSUS_ERROR"


class ReplicationError(NetworkError):
    code = "REPLICATION_ERROR"


class SerializationError(ZyraError):
    code = "SERIALIZATION_ERROR"


class ProtocolError(NetworkError):
    code = "PROTOCOL_ERROR"

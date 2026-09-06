from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


class ConfigurationError(ValueError):
    """Raised when required configuration is invalid."""


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if value is None or not value.strip():
        raise ConfigurationError(f"Required configuration is missing: {name}")
    return value.strip()


def _positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigurationError(
            f"{name} must be an integer"
        ) from exc

    if parsed <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")

    return parsed


@dataclass(frozen=True, slots=True)
class NetworkConfig:
    environment: str
    service_name: str
    node_id: str | None
    host: str
    port: int
    log_level: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "NetworkConfig":
        source = os.environ if env is None else env

        environment = source.get("ZYRA_ENV", "production").strip().lower()
        if environment not in {"development", "testing", "staging", "production"}:
            raise ConfigurationError(
                "ZYRA_ENV must be development, testing, staging, or production"
            )

        service_name = source.get(
            "ZYRA_SERVICE_NAME",
            "zyra-network",
        ).strip()

        if not service_name:
            raise ConfigurationError("ZYRA_SERVICE_NAME cannot be empty")

        host = source.get("ZYRA_HOST", "0.0.0.0").strip()
        port = _positive_int(
            source.get("ZYRA_PORT", "8000"),
            "ZYRA_PORT",
        )

        log_level = source.get("ZYRA_LOG_LEVEL", "INFO").strip().upper()
        allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

        if log_level not in allowed_levels:
            raise ConfigurationError(
                "ZYRA_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL"
            )

        node_id = source.get("ZYRA_NODE_ID")
        if node_id is not None:
            node_id = node_id.strip() or None

        return cls(
            environment=environment,
            service_name=service_name,
            node_id=node_id,
            host=host,
            port=port,
            log_level=log_level,
        )


__all__ = ["ConfigurationError", "NetworkConfig"]

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class ConfigurationError(ValueError):
    """Raised when infrastructure configuration is invalid."""


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"

    @classmethod
    def parse(cls, value: str) -> "Environment":
        normalized = value.strip().lower()

        aliases = {
            "dev": cls.DEVELOPMENT,
            "development": cls.DEVELOPMENT,
            "test": cls.TESTING,
            "testing": cls.TESTING,
            "stage": cls.STAGING,
            "staging": cls.STAGING,
            "prod": cls.PRODUCTION,
            "production": cls.PRODUCTION,
        }

        try:
            return aliases[normalized]
        except KeyError as exc:
            raise ConfigurationError(
                f"Unsupported environment: {value}"
            ) from exc


def _parse_bool(
    value: str,
    name: str,
) -> bool:
    normalized = value.strip().lower()

    if normalized in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True

    if normalized in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False

    raise ConfigurationError(
        f"{name} must be a boolean value"
    )


def _parse_positive_int(
    value: str,
    name: str,
) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigurationError(
            f"{name} must be an integer"
        ) from exc

    if parsed <= 0:
        raise ConfigurationError(
            f"{name} must be greater than zero"
        )

    return parsed


def _parse_non_negative_int(
    value: str,
    name: str,
) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigurationError(
            f"{name} must be an integer"
        ) from exc

    if parsed < 0:
        raise ConfigurationError(
            f"{name} cannot be negative"
        )

    return parsed


@dataclass(frozen=True, slots=True)
class Configuration:
    environment: Environment
    service_name: str
    node_id: str
    data_directory: str
    database_path: str
    cache_capacity: int
    cache_default_ttl_seconds: int
    database_timeout_seconds: int
    database_wal: bool
    shutdown_timeout_seconds: int
    strict_configuration: bool

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, str],
    ) -> "Configuration":

        environment = Environment.parse(
            values.get(
                "ZYRA_ENVIRONMENT",
                "production",
            )
        )

        service_name = values.get(
            "ZYRA_SERVICE_NAME",
            "zyra-network",
        ).strip()

        node_id = values.get(
            "ZYRA_NODE_ID",
            "node-default",
        ).strip()

        data_directory = values.get(
            "ZYRA_DATA_DIRECTORY",
            "./data",
        ).strip()

        database_path = values.get(
            "ZYRA_DATABASE_PATH",
            "./data/zyra.db",
        ).strip()

        if not service_name:
            raise ConfigurationError(
                "ZYRA_SERVICE_NAME cannot be empty"
            )

        if not node_id:
            raise ConfigurationError(
                "ZYRA_NODE_ID cannot be empty"
            )

        if not data_directory:
            raise ConfigurationError(
                "ZYRA_DATA_DIRECTORY cannot be empty"
            )

        if not database_path:
            raise ConfigurationError(
                "ZYRA_DATABASE_PATH cannot be empty"
            )

        return cls(
            environment=environment,
            service_name=service_name,
            node_id=node_id,
            data_directory=data_directory,
            database_path=database_path,
            cache_capacity=_parse_positive_int(
                values.get(
                    "ZYRA_CACHE_CAPACITY",
                    "4096",
                ),
                "ZYRA_CACHE_CAPACITY",
            ),
            cache_default_ttl_seconds=_parse_positive_int(
                values.get(
                    "ZYRA_CACHE_DEFAULT_TTL_SECONDS",
                    "300",
                ),
                "ZYRA_CACHE_DEFAULT_TTL_SECONDS",
            ),
            database_timeout_seconds=_parse_positive_int(
                values.get(
                    "ZYRA_DATABASE_TIMEOUT_SECONDS",
                    "30",
                ),
                "ZYRA_DATABASE_TIMEOUT_SECONDS",
            ),
            database_wal=_parse_bool(
                values.get(
                    "ZYRA_DATABASE_WAL",
                    "true",
                ),
                "ZYRA_DATABASE_WAL",
            ),
            shutdown_timeout_seconds=_parse_non_negative_int(
                values.get(
                    "ZYRA_SHUTDOWN_TIMEOUT_SECONDS",
                    "30",
                ),
                "ZYRA_SHUTDOWN_TIMEOUT_SECONDS",
            ),
            strict_configuration=_parse_bool(
                values.get(
                    "ZYRA_STRICT_CONFIGURATION",
                    "true",
                ),
                "ZYRA_STRICT_CONFIGURATION",
            ),
        )

    @classmethod
    def from_environment(
        cls,
    ) -> "Configuration":
        return cls.from_mapping(os.environ)

    def require_production_safe(self) -> None:
        if self.environment is not Environment.PRODUCTION:
            return

        if not self.strict_configuration:
            raise ConfigurationError(
                "Strict configuration must be enabled in production"
            )

        if self.node_id == "node-default":
            raise ConfigurationError(
                "ZYRA_NODE_ID must be explicitly configured in production"
            )

        if self.service_name == "zyra-network":
            raise ConfigurationError(
                "ZYRA_SERVICE_NAME must be explicitly configured in production"
            )


__all__ = [
    "Configuration",
    "ConfigurationError",
    "Environment",
]

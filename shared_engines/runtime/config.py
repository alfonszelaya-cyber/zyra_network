"""Validated runtime configuration.

``port=0`` is valid and standard: it asks the OS for an
ephemeral free port (tests and orchestrators rely on it).
The API token is runtime state injected by the composition
root; it is never hardcoded.
"""
from __future__ import annotations

from dataclasses import dataclass

from shared_engines.common.errors import ConfigurationError
from shared_engines.common.validation import (
    require_int_range,
    require_non_empty_str,
)


@dataclass(frozen=True)
class RuntimeConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    max_body_bytes: int = 1_000_000
    api_token: str | None = None

    def __post_init__(self) -> None:
        require_non_empty_str(self.host, "host", config=True)
        if not isinstance(self.port, int) or isinstance(
            self.port, bool
        ):
            raise ConfigurationError("port must be an integer")
        if not 0 <= self.port <= 65535:
            raise ConfigurationError(
                "port must be in [0, 65535] (0 = ephemeral)"
            )
        require_int_range(
            self.max_body_bytes,
            "max_body_bytes",
            1,
            50_000_000,
            config=True,
        )
        if self.api_token is not None and len(self.api_token) < 16:
            raise ConfigurationError(
                "api_token must be at least 16 characters"
            )

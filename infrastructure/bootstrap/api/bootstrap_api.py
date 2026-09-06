"""Stable API facade over the Infrastructure composition root."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ..bootstrap import InfrastructureBootstrap
from ...config import Configuration


@dataclass(frozen=True, slots=True)
class BootstrapRequest:
    configuration: Configuration
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BootstrapResponse:
    accepted: bool
    environment: str
    service_name: str
    node_id: str
    message: str


class BootstrapService:
    """
    Public service facade for starting and stopping Infrastructure.

    The composition root remains InfrastructureBootstrap. This
    service provides a stable API boundary without introducing
    provider-specific dependencies.
    """

    def __init__(self) -> None:
        self._bootstrap: InfrastructureBootstrap | None = None

    def start(
        self,
        request: BootstrapRequest,
    ) -> BootstrapResponse:
        if not isinstance(
            request.configuration,
            Configuration,
        ):
            raise TypeError(
                "request.configuration must be Configuration"
            )

        configuration = request.configuration

        self._bootstrap = InfrastructureBootstrap(
            configuration
        )

        self._bootstrap.initialize()

        return BootstrapResponse(
            accepted=True,
            environment=configuration.environment.value,
            service_name=configuration.service_name,
            node_id=configuration.node_id,
            message="Infrastructure initialized",
        )

    def stop(self) -> None:
        if self._bootstrap is not None:
            self._bootstrap.shutdown()
            self._bootstrap = None


__all__ = [
    "BootstrapRequest",
    "BootstrapResponse",
    "BootstrapService",
]

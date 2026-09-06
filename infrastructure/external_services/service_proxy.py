from __future__ import annotations

from typing import Any, Mapping

from .service_adapter import (
    ServiceAdapter,
    ServiceRequest,
    ServiceResponse,
)
from .timeout_manager import (
    TimeoutManager,
)


class ServiceProxy:
    """
    Controlled proxy boundary around an external adapter.

    The proxy owns request normalization and timeout policy;
    transport implementation remains delegated to the adapter.
    """

    def __init__(
        self,
        adapter: ServiceAdapter,
        *,
        timeout_manager: TimeoutManager | None = None,
    ) -> None:

        if not isinstance(
            adapter,
            ServiceAdapter,
        ):
            raise TypeError(
                "adapter must implement ServiceAdapter"
            )

        self.adapter = adapter
        self.timeout_manager = (
            timeout_manager
            or TimeoutManager()
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        body: bytes | None = None,
    ) -> ServiceResponse:

        request = ServiceRequest(
            method=method,
            path=path,
            headers=headers or {},
            body=body,
        )

        return self.adapter.send(
            request
        )

    def close(self) -> None:
        self.adapter.close()


__all__ = ["ServiceProxy"]

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ServiceRequest:
    method: str
    path: str
    headers: Mapping[str, str]
    body: bytes | None = None

    def __post_init__(self) -> None:
        method = self.method.strip().upper()
        path = self.path.strip()

        if not method:
            raise ValueError(
                "Service request method cannot be empty"
            )

        if not path:
            raise ValueError(
                "Service request path cannot be empty"
            )

        object.__setattr__(
            self,
            "method",
            method,
        )

        object.__setattr__(
            self,
            "path",
            path,
        )

        object.__setattr__(
            self,
            "headers",
            dict(self.headers),
        )


@dataclass(frozen=True, slots=True)
class ServiceResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes

    def __post_init__(self) -> None:
        if not 100 <= self.status_code <= 599:
            raise ValueError(
                "Invalid HTTP-style status code"
            )

        object.__setattr__(
            self,
            "headers",
            dict(self.headers),
        )

        object.__setattr__(
            self,
            "body",
            bytes(self.body),
        )


class ServiceAdapter(ABC):

    @abstractmethod
    def send(
        self,
        request: ServiceRequest,
    ) -> ServiceResponse:
        raise NotImplementedError

    def close(self) -> None:
        pass


__all__ = [
    "ServiceRequest",
    "ServiceResponse",
    "ServiceAdapter",
]

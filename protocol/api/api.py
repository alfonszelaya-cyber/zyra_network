from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class APIRequest:
    method: str
    path: str
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""

    def __post_init__(self) -> None:
        method = self.method.strip().upper()
        path = self.path.strip()

        if not method:
            raise ValueError("API method cannot be empty")
        if not path.startswith("/"):
            raise ValueError("API path must start with '/'")

        object.__setattr__(self, "method", method)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "headers", dict(self.headers))


@dataclass(frozen=True, slots=True)
class APIResponse:
    status_code: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""

    def __post_init__(self) -> None:
        if not 100 <= self.status_code <= 599:
            raise ValueError("Invalid HTTP status code")

        object.__setattr__(self, "headers", dict(self.headers))


class APIRouter:
    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], object] = {}

    def register(
        self,
        method: str,
        path: str,
        handler: object,
    ) -> None:
        if not callable(handler):
            raise TypeError("API handler must be callable")

        key = (method.strip().upper(), path.strip())

        if not key[1].startswith("/"):
            raise ValueError("API path must start with '/'")

        if key in self._routes:
            raise ValueError(f"Route already registered: {key}")

        self._routes[key] = handler

    def resolve(self, method: str, path: str) -> object:
        key = (method.strip().upper(), path.strip())

        try:
            return self._routes[key]
        except KeyError as exc:
            raise LookupError(f"API route not found: {key}") from exc

    def routes(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._routes))


__all__ = ["APIRequest", "APIResponse", "APIRouter"]

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class Endpoint:
    name: str
    address: str
    port: int
    secure: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError(
                "Endpoint name cannot be empty"
            )

        if not self.address.strip():
            raise ValueError(
                "Endpoint address cannot be empty"
            )

        if not 1 <= self.port <= 65535:
            raise ValueError(
                "Endpoint port out of range"
            )


class EndpointDirectory:
    def __init__(self) -> None:
        self._endpoints: dict[
            str,
            Endpoint,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        endpoint: Endpoint,
        *,
        replace: bool = False,
    ) -> None:

        key = endpoint.name.strip().lower()

        with self._lock:
            if (
                key in self._endpoints
                and not replace
            ):
                raise ValueError(
                    f"Endpoint already exists: {key}"
                )

            self._endpoints[key] = endpoint

    def get(
        self,
        name: str,
    ) -> Endpoint:

        with self._lock:
            try:
                return self._endpoints[
                    name.strip().lower()
                ]
            except KeyError as exc:
                raise LookupError(
                    f"Endpoint not found: {name}"
                ) from exc

    def remove(
        self,
        name: str,
    ) -> bool:

        with self._lock:
            return (
                self._endpoints.pop(
                    name.strip().lower(),
                    None,
                )
                is not None
            )

    def list(
        self,
    ) -> tuple[Endpoint, ...]:

        with self._lock:
            return tuple(
                self._endpoints[name]
                for name in sorted(
                    self._endpoints
                )
            )


__all__ = [
    "Endpoint",
    "EndpointDirectory",
]

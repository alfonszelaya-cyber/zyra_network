from __future__ import annotations

import socket
from typing import Callable

from .dns_cache import DNSCache
from .dns_validator import DNSValidator


Resolver = Callable[
    [str, int, int],
    tuple[str, ...],
]


class DNSResolver:
    def __init__(
        self,
        *,
        cache: DNSCache | None = None,
        resolver: Resolver | None = None,
        default_ttl_seconds: int = 300,
    ) -> None:

        if default_ttl_seconds <= 0:
            raise ValueError(
                "default_ttl_seconds must be positive"
            )

        self.cache = cache or DNSCache()
        self.validator = DNSValidator()
        self._resolver = (
            resolver
            or self._system_resolver
        )
        self.default_ttl_seconds = (
            default_ttl_seconds
        )

    @staticmethod
    def _system_resolver(
        hostname: str,
        family: int,
        socktype: int,
    ) -> tuple[str, ...]:

        results = socket.getaddrinfo(
            hostname,
            None,
            family,
            socktype,
        )

        addresses = {
            result[4][0]
            for result in results
        }

        return tuple(
            sorted(addresses)
        )

    def resolve(
        self,
        hostname: str,
    ) -> tuple[str, ...]:

        normalized = (
            self.validator
            .validate_hostname(hostname)
        )

        cached = self.cache.get(
            normalized
        )

        if cached is not None:
            return cached

        addresses = self._resolver(
            normalized,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
        )

        if not addresses:
            raise LookupError(
                f"DNS resolution returned no addresses: "
                f"{normalized}"
            )

        self.cache.put(
            normalized,
            tuple(addresses),
            self.default_ttl_seconds,
        )

        return tuple(addresses)


__all__ = [
    "DNSResolver",
    "Resolver",
]

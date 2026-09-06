from __future__ import annotations

from dataclasses import dataclass

from .dns_registry import DNSRegistry
from .dns_resolver import DNSResolver


@dataclass(frozen=True, slots=True)
class DNSResolution:
    hostname: str
    addresses: tuple[str, ...]
    source: str


class DNSEngine:
    def __init__(
        self,
        *,
        registry: DNSRegistry | None = None,
        resolver: DNSResolver | None = None,
    ) -> None:

        self.registry = registry or DNSRegistry()
        self.resolver = resolver or DNSResolver()

    def resolve(
        self,
        hostname: str,
    ) -> DNSResolution:

        normalized = hostname.strip().lower()

        try:
            record = self.registry.resolve(
                normalized
            )

            return DNSResolution(
                hostname=normalized,
                addresses=record.addresses,
                source="registry",
            )
        except LookupError:
            addresses = self.resolver.resolve(
                normalized
            )

            return DNSResolution(
                hostname=normalized,
                addresses=addresses,
                source="resolver",
            )


__all__ = [
    "DNSResolution",
    "DNSEngine",
]

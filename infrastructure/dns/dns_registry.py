from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class DNSRecord:
    hostname: str
    addresses: tuple[str, ...]
    ttl_seconds: int = 300

    def __post_init__(self) -> None:
        if not self.hostname.strip():
            raise ValueError(
                "DNS hostname cannot be empty"
            )

        if not self.addresses:
            raise ValueError(
                "DNS record must contain addresses"
            )

        if self.ttl_seconds <= 0:
            raise ValueError(
                "DNS TTL must be positive"
            )


class DNSRegistry:
    def __init__(self) -> None:
        self._records: dict[
            str,
            DNSRecord,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        record: DNSRecord,
        *,
        replace: bool = False,
    ) -> None:

        hostname = record.hostname.lower()

        with self._lock:
            if (
                hostname in self._records
                and not replace
            ):
                raise ValueError(
                    f"DNS record already exists: {hostname}"
                )

            self._records[hostname] = record

    def resolve(
        self,
        hostname: str,
    ) -> DNSRecord:

        with self._lock:
            try:
                return self._records[
                    hostname.strip().lower()
                ]
            except KeyError as exc:
                raise LookupError(
                    f"DNS record not found: {hostname}"
                ) from exc

    def remove(
        self,
        hostname: str,
    ) -> bool:

        with self._lock:
            return (
                self._records.pop(
                    hostname.strip().lower(),
                    None,
                )
                is not None
            )

    def list(
        self,
    ) -> tuple[DNSRecord, ...]:

        with self._lock:
            return tuple(
                self._records[name]
                for name in sorted(
                    self._records
                )
            )


__all__ = [
    "DNSRecord",
    "DNSRegistry",
]

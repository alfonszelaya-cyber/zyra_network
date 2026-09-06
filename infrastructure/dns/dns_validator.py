from __future__ import annotations

import ipaddress
import re


class DNSValidator:
    _HOSTNAME = re.compile(
        r"^(?=.{1,253}$)"
        r"(?:[A-Za-z0-9]"
        r"(?:[A-Za-z0-9-]{0,61}"
        r"[A-Za-z0-9])?\.)*"
        r"[A-Za-z0-9]"
        r"(?:[A-Za-z0-9-]{0,61}"
        r"[A-Za-z0-9])?$"
    )

    def validate_hostname(
        self,
        hostname: str,
    ) -> str:

        normalized = hostname.strip().rstrip(".")

        if not normalized:
            raise ValueError(
                "Hostname cannot be empty"
            )

        if not self._HOSTNAME.fullmatch(
            normalized
        ):
            raise ValueError(
                f"Invalid hostname: {hostname}"
            )

        return normalized.lower()

    def validate_ip(
        self,
        address: str,
    ) -> str:

        normalized = address.strip()

        try:
            ipaddress.ip_address(
                normalized
            )
        except ValueError as exc:
            raise ValueError(
                f"Invalid IP address: {address}"
            ) from exc

        return normalized


__all__ = ["DNSValidator"]

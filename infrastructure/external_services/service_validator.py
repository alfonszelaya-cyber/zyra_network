from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class ServiceValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()


class ServiceValidator:
    ALLOWED_SCHEMES = frozenset(
        {
            "http",
            "https",
            "grpc",
            "grpcs",
        }
    )

    def validate_url(
        self,
        url: str,
    ) -> ServiceValidationResult:

        errors: list[str] = []

        if not isinstance(url, str):
            return ServiceValidationResult(
                False,
                ("URL must be a string",),
            )

        parsed = urlparse(
            url.strip()
        )

        if parsed.scheme not in self.ALLOWED_SCHEMES:
            errors.append(
                "unsupported service URL scheme"
            )

        if not parsed.hostname:
            errors.append(
                "service URL must contain a hostname"
            )

        if parsed.username or parsed.password:
            errors.append(
                "credentials are not allowed in service URLs"
            )

        return ServiceValidationResult(
            not errors,
            tuple(errors),
        )

    def require_valid_url(
        self,
        url: str,
    ) -> None:

        result = self.validate_url(url)

        if not result.valid:
            raise ValueError(
                "; ".join(result.errors)
            )


__all__ = [
    "ServiceValidationResult",
    "ServiceValidator",
]

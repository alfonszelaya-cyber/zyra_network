from __future__ import annotations

import secrets

from .identifier import Identifier
from .namespace import Namespace


def generate_id(
    namespace: Namespace | str,
) -> Identifier:
    """
    Generate a cryptographically strong 128-bit identifier.

    secrets.token_hex() uses the operating system's secure
    randomness source and is appropriate for identifiers where
    unpredictability is required.
    """

    if isinstance(namespace, Namespace):
        namespace_value = namespace.value
    elif isinstance(namespace, str):
        namespace_value = namespace.strip().lower()
    else:
        raise TypeError(
            "namespace must be Namespace or string"
        )

    if not namespace_value:
        raise ValueError("namespace cannot be empty")

    if len(namespace_value) > 64:
        raise ValueError(
            "namespace cannot exceed 64 characters"
        )

    if not namespace_value[0].isalnum():
        raise ValueError(
            "namespace must start with an alphanumeric character"
        )

    for char in namespace_value:
        if not (
            char.isalnum()
            or char in {"-", "_"}
        ):
            raise ValueError(
                "namespace contains invalid characters"
            )

    value = (
        f"zyra_{namespace_value}_"
        f"{secrets.token_hex(16)}"
    )

    return Identifier(value)

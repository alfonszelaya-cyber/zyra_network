from __future__ import annotations

from abc import abstractmethod
from typing import Any, ClassVar, Mapping

from .base import Contract, ContractViolation


class VersionedContract(Contract):
    """
    Contract with explicit compatibility boundaries.
    """

    minimum_supported_version: ClassVar[int] = 1

    @classmethod
    def validate_version(cls, version: int) -> None:
        if not isinstance(version, int):
            raise ContractViolation(
                "Contract version must be an integer"
            )

        if version < cls.minimum_supported_version:
            raise ContractViolation(
                f"Unsupported contract version: {version}"
            )

        if version > cls.contract_version:
            raise ContractViolation(
                f"Future contract version: {version}"
            )

    @classmethod
    @abstractmethod
    def migrate(
        cls,
        value: Mapping[str, Any],
        from_version: int,
    ) -> Mapping[str, Any]:
        """Upgrade an older representation."""
        raise NotImplementedError

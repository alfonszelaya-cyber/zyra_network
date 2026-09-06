from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Mapping


class ContractViolation(ValueError):
    """Raised when data violates a declared contract."""


class Contract(ABC):
    """Base contract for stable ZYRA boundaries."""

    contract_name: ClassVar[str]
    contract_version: ClassVar[int] = 1

    @classmethod
    @abstractmethod
    def validate(cls, value: Any) -> None:
        """Validate a value against the contract."""

    @classmethod
    @abstractmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Contract":
        """Construct a contract from a mapping."""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize the contract."""

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return {
            "name": cls.contract_name,
            "version": cls.contract_version,
        }

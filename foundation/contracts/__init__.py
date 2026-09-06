"""
ZYRA Foundation Contracts.

Stable contracts used as boundaries between Network components,
infrastructure adapters and applications.
"""

from .base import Contract, ContractViolation
from .registry import ContractRegistry
from .result import Result
from .serialization import (
    ContractSerializationError,
    from_json,
    to_json,
)
from .versioned import VersionedContract

__all__ = [
    "Contract",
    "ContractViolation",
    "ContractRegistry",
    "Result",
    "VersionedContract",
    "ContractSerializationError",
    "to_json",
    "from_json",
]

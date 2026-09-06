"""
ZYRA Foundation - Universal Identity/ID primitives.

This package provides immutable, sortable, cryptographically strong
identifiers used throughout the ZYRA Network.
"""

from .generator import generate_id
from .identifier import Identifier
from .namespace import Namespace

__all__ = [
    "Identifier",
    "Namespace",
    "generate_id",
]

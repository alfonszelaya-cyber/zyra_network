"""
ZYRA Foundation Context.

Provides immutable execution context primitives shared by the
Network, transversal engines and applications.
"""

from .context import Context
from .scope import ContextScope
from .correlation import CorrelationContext
from .manager import ContextManager

__all__ = [
    "Context",
    "ContextScope",
    "CorrelationContext",
    "ContextManager",
]

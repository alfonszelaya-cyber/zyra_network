"""Zyra runtime: kernel + HTTP API.

The kernel is the composition root: it wires storage,
events, audit, identity and verification into ONE living
system, bootstraps the Root Authority identity, and exposes
aggregated health. The API layer serves that system over
HTTP with bearer-token auth, strict error mapping and a
stable JSON envelope, so third parties (apps, banks,
external verifiers) can consume the Network.
"""
from __future__ import annotations

from shared_engines.runtime.api import ZyraApiHandler
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.runtime.responses import ApiError
from shared_engines.runtime.server import ZyraServer

__all__ = [
    "ApiError", "RuntimeConfig", "ZyraApiHandler",
    "ZyraKernel", "ZyraServer",
]

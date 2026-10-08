"""Shim de compatibilidad (regla 51): implementacion canonica en shared_engines.network.network_client (NetworkClient x7 -> 1). Variante original preservada en shared_engines/network/legacy_variants/."""
from shared_engines.network.network_client import *  # noqa: F401,F403
from shared_engines.network.network_client import NetworkClient  # noqa: F401

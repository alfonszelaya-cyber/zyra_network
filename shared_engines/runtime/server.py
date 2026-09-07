"""Threaded HTTP server bound to the Zyra API handler."""
from __future__ import annotations

from http.server import ThreadingHTTPServer

from shared_engines.runtime.api import ZyraApiHandler


class ZyraServer(ThreadingHTTPServer):
    """Daemon-threaded server; bind via ZyraApiHandler ClassVars."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int]) -> None:
        super().__init__(address, ZyraApiHandler)

    @property
    def bound_port(self) -> int:
        """The actual port bound (useful when port=0/ephemeral)."""
        return int(self.server_address[1])

from __future__ import annotations

from ..core import (
    ObservationManager,
)


class MonitoringService:
    def __init__(
        self,
        manager: ObservationManager,
    ) -> None:

        self.manager = manager

    def start(self) -> None:
        self.manager.start()

    def stop(self) -> None:
        self.manager.stop()

    def status(self) -> dict:
        return self.manager.status()

    def healthy(self) -> bool:
        status = self.manager.status()

        return status["state"] == "running"


__all__ = ["MonitoringService"]

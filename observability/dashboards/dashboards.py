from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class DashboardWidget:
    widget_id: str
    title: str
    query: str
    options: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(frozen=True, slots=True)
class Dashboard:
    dashboard_id: str
    name: str
    widgets: tuple[
        DashboardWidget,
        ...,
    ] = ()


class DashboardRegistry:
    def __init__(self) -> None:
        self._dashboards: dict[
            str,
            Dashboard,
        ] = {}

    def register(
        self,
        dashboard: Dashboard,
    ) -> None:

        self._dashboards[
            dashboard.dashboard_id
        ] = dashboard

    def unregister(
        self,
        dashboard_id: str,
    ) -> None:

        self._dashboards.pop(
            dashboard_id,
            None,
        )

    def get(
        self,
        dashboard_id: str,
    ) -> Dashboard | None:

        return self._dashboards.get(
            dashboard_id
        )

    def all(self) -> list[Dashboard]:
        return list(
            self._dashboards.values()
        )


__all__ = [
    "Dashboard",
    "DashboardRegistry",
    "DashboardWidget",
]

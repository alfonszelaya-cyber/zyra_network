
"""Nexo Support Case Engine - casos transversales
que incluyen NEXO (delega al transversal)."""
from __future__ import annotations

class NexoSupportCaseEngine:
    """Casos cross-app con NEXO incluido."""

    def __init__(self, support_engine,
                 app_id="nexo"):
        self._support = support_engine
        self._app = app_id

    def open_case(self, *, apps_involved, title,
                  case_data=None) -> dict:
        apps = [self._app] + [a for a in
                apps_involved
                if a != self._app]
        return (self._support.
                create_cross_app_case(
                    apps_involved=apps,
                    title=title,
                    case_data=case_data))

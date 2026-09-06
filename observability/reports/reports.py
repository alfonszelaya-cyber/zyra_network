from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..core import utc_iso, utc_now


@dataclass(frozen=True, slots=True)
class ObservationReport:
    generated_at: str
    title: str
    summary: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "title": self.title,
            "summary": dict(
                self.summary
            ),
        }


class ReportBuilder:
    def build(
        self,
        title: str,
        summary: Mapping[str, Any],
    ) -> ObservationReport:

        return ObservationReport(
            generated_at=utc_iso(
                utc_now()
            ),
            title=title,
            summary=dict(summary),
        )


__all__ = [
    "ObservationReport",
    "ReportBuilder",
]

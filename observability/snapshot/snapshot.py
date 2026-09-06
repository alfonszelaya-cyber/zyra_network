from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from ..core import utc_iso, utc_now


@dataclass(frozen=True, slots=True)
class ObservationSnapshot:
    captured_at: datetime
    payload: Mapping[str, Any]

    @classmethod
    def capture(
        cls,
        payload: Mapping[str, Any],
    ) -> "ObservationSnapshot":

        return cls(
            captured_at=utc_now(),
            payload=dict(payload),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "captured_at": utc_iso(
                self.captured_at
            ),
            "payload": dict(
                self.payload
            ),
        }


__all__ = ["ObservationSnapshot"]

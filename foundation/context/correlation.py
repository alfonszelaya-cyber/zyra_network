from __future__ import annotations

from dataclasses import dataclass

from foundation.ids import generate_id


@dataclass(frozen=True, slots=True)
class CorrelationContext:
    """
    Correlates distributed operations across services,
    nodes, events and asynchronous workflows.
    """

    correlation_id: str
    causation_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        causation_id: str | None = None,
    ) -> "CorrelationContext":
        return cls(
            correlation_id=str(
                generate_id("correlation")
            ),
            causation_id=causation_id,
        )

    def child(
        self,
        *,
        causation_id: str | None = None,
    ) -> "CorrelationContext":
        return CorrelationContext(
            correlation_id=self.correlation_id,
            causation_id=(
                causation_id
                or self.correlation_id
            ),
        )

    def to_headers(self) -> dict[str, str]:
        headers = {
            "x-zyra-correlation-id":
                self.correlation_id,
        }

        if self.causation_id:
            headers["x-zyra-causation-id"] = (
                self.causation_id
            )

        return headers

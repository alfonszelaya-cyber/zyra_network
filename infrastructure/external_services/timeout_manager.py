from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimeoutPolicy:
    connect_seconds: float = 5.0
    read_seconds: float = 30.0
    write_seconds: float = 30.0
    total_seconds: float = 60.0

    def __post_init__(self) -> None:
        values = (
            self.connect_seconds,
            self.read_seconds,
            self.write_seconds,
            self.total_seconds,
        )

        if any(
            value <= 0
            for value in values
        ):
            raise ValueError(
                "Timeout values must be positive"
            )

        if (
            self.total_seconds
            < self.connect_seconds
        ):
            raise ValueError(
                "total_seconds cannot be smaller "
                "than connect_seconds"
            )


class TimeoutManager:
    def __init__(
        self,
        policy: TimeoutPolicy | None = None,
    ) -> None:
        self.policy = (
            policy
            or TimeoutPolicy()
        )

    def connect_timeout(self) -> float:
        return self.policy.connect_seconds

    def read_timeout(self) -> float:
        return self.policy.read_seconds

    def write_timeout(self) -> float:
        return self.policy.write_seconds

    def total_timeout(self) -> float:
        return self.policy.total_seconds


__all__ = [
    "TimeoutPolicy",
    "TimeoutManager",
]

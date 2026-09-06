from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 0.25
    multiplier: float = 2.0
    max_delay_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_attempts <= 0:
            raise ValueError(
                "max_attempts must be positive"
            )

        if self.initial_delay_seconds < 0:
            raise ValueError(
                "initial_delay_seconds cannot be negative"
            )

        if self.multiplier < 1:
            raise ValueError(
                "multiplier must be at least 1"
            )

        if self.max_delay_seconds < 0:
            raise ValueError(
                "max_delay_seconds cannot be negative"
            )


class RetryManager:
    def __init__(
        self,
        policy: RetryPolicy | None = None,
    ) -> None:
        self.policy = policy or RetryPolicy()

    def delay_for(
        self,
        attempt: int,
    ) -> float:

        if attempt < 1:
            raise ValueError(
                "attempt must be positive"
            )

        delay = (
            self.policy.initial_delay_seconds
            * (
                self.policy.multiplier
                ** (attempt - 1)
            )
        )

        return min(
            delay,
            self.policy.max_delay_seconds,
        )

    def execute(
        self,
        operation,
    ):
        last_error: BaseException | None = None

        for attempt in range(
            1,
            self.policy.max_attempts + 1,
        ):
            try:
                return operation()
            except BaseException as exc:
                last_error = exc

                if (
                    attempt
                    >= self.policy.max_attempts
                ):
                    break

                delay = self.delay_for(
                    attempt
                )

                if delay > 0:
                    time.sleep(delay)

        assert last_error is not None
        raise last_error


__all__ = [
    "RetryPolicy",
    "RetryManager",
]

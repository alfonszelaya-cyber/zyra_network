from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    max_age_days: int = 30
    max_backups: int = 100

    def __post_init__(self) -> None:
        if self.max_age_days <= 0:
            raise ValueError(
                "max_age_days must be positive"
            )

        if self.max_backups <= 0:
            raise ValueError(
                "max_backups must be positive"
            )

    def expiration_time(
        self,
        created_at: datetime,
    ) -> datetime:

        if created_at.tzinfo is None:
            raise ValueError(
                "created_at must be timezone-aware"
            )

        return (
            created_at.astimezone(
                timezone.utc
            )
            + timedelta(
                days=self.max_age_days
            )
        )

    def is_expired(
        self,
        created_at: datetime,
        *,
        now: datetime | None = None,
    ) -> bool:

        current = (
            now
            or datetime.now(timezone.utc)
        )

        return current >= self.expiration_time(
            created_at
        )


__all__ = ["RetentionPolicy"]

from __future__ import annotations

from dataclasses import dataclass

from ..core import (
    RetentionPolicy,
    ValidationError,
)


@dataclass(frozen=True, slots=True)
class ObservationPolicy:
    retention: RetentionPolicy
    max_attributes: int = 64
    max_attribute_length: int = 8192

    def __post_init__(self) -> None:
        if self.max_attributes <= 0:
            raise ValidationError(
                "max_attributes must be positive"
            )

        if self.max_attribute_length <= 0:
            raise ValidationError(
                "max_attribute_length must be positive"
            )

    def validate_attributes(
        self,
        attributes: dict,
    ) -> dict:
        result = {}

        for key, value in list(
            attributes.items()
        )[: self.max_attributes]:

            result[str(key)[:256]] = str(
                value
            )[: self.max_attribute_length]

        return result


__all__ = [
    "ObservationPolicy",
    "RetentionPolicy",
]

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class MessageValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()

    @classmethod
    def ok(cls) -> "MessageValidationResult":
        return cls(True, ())

    @classmethod
    def invalid(
        cls,
        *errors: str,
    ) -> "MessageValidationResult":
        return cls(False, tuple(errors))


class MessageValidator:
    MAX_TOPIC_LENGTH = 512
    MAX_PAYLOAD_KEYS = 10000

    def validate(
        self,
        topic: str,
        payload: Mapping[str, Any],
    ) -> MessageValidationResult:

        errors: list[str] = []

        if not isinstance(topic, str):
            errors.append(
                "topic must be a string"
            )
        else:
            normalized = topic.strip()

            if not normalized:
                errors.append(
                    "topic cannot be empty"
                )

            if len(normalized) > self.MAX_TOPIC_LENGTH:
                errors.append(
                    "topic exceeds maximum length"
                )

        if not isinstance(payload, Mapping):
            errors.append(
                "payload must be a mapping"
            )
        elif len(payload) > self.MAX_PAYLOAD_KEYS:
            errors.append(
                "payload contains too many keys"
            )

        if errors:
            return MessageValidationResult.invalid(
                *errors
            )

        return MessageValidationResult.ok()

    def require_valid(
        self,
        topic: str,
        payload: Mapping[str, Any],
    ) -> None:

        result = self.validate(
            topic,
            payload,
        )

        if not result.valid:
            raise ValueError(
                "; ".join(result.errors)
            )


__all__ = [
    "MessageValidationResult",
    "MessageValidator",
]

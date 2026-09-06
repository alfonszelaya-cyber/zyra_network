from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Callable


class ValidationFailure(ValueError):
    """Raised when validation fails."""


class Validator:
    """Composable production validation primitives."""

    @staticmethod
    def required(
        value: Any,
        field: str,
    ) -> Any:
        if value is None:
            raise ValidationFailure(
                f"{field} is required"
            )

        if (
            isinstance(value, str)
            and not value.strip()
        ):
            raise ValidationFailure(
                f"{field} cannot be empty"
            )

        return value

    @staticmethod
    def string(
        value: Any,
        field: str,
        *,
        min_length: int | None = None,
        max_length: int | None = None,
    ) -> str:
        if not isinstance(value, str):
            raise ValidationFailure(
                f"{field} must be a string"
            )

        length = len(value)

        if (
            min_length is not None
            and length < min_length
        ):
            raise ValidationFailure(
                f"{field} is too short"
            )

        if (
            max_length is not None
            and length > max_length
        ):
            raise ValidationFailure(
                f"{field} is too long"
            )

        return value

    @staticmethod
    def integer(
        value: Any,
        field: str,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
        ):
            raise ValidationFailure(
                f"{field} must be an integer"
            )

        if (
            minimum is not None
            and value < minimum
        ):
            raise ValidationFailure(
                f"{field} is below minimum"
            )

        if (
            maximum is not None
            and value > maximum
        ):
            raise ValidationFailure(
                f"{field} exceeds maximum"
            )

        return value

    @staticmethod
    def number(
        value: Any,
        field: str,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> int | float:
        if (
            isinstance(value, bool)
            or not isinstance(
                value,
                (int, float),
            )
        ):
            raise ValidationFailure(
                f"{field} must be numeric"
            )

        numeric = float(value)

        if (
            minimum is not None
            and numeric < minimum
        ):
            raise ValidationFailure(
                f"{field} is below minimum"
            )

        if (
            maximum is not None
            and numeric > maximum
        ):
            raise ValidationFailure(
                f"{field} exceeds maximum"
            )

        return value

    @staticmethod
    def boolean(
        value: Any,
        field: str,
    ) -> bool:
        if not isinstance(value, bool):
            raise ValidationFailure(
                f"{field} must be boolean"
            )

        return value

    @staticmethod
    def mapping(
        value: Any,
        field: str,
    ) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise ValidationFailure(
                f"{field} must be an object"
            )

        return value

    @staticmethod
    def sequence(
        value: Any,
        field: str,
    ) -> Sequence[Any]:
        if (
            isinstance(value, (str, bytes))
            or not isinstance(
                value,
                Sequence,
            )
        ):
            raise ValidationFailure(
                f"{field} must be a sequence"
            )

        return value

    @staticmethod
    def one_of(
        value: Any,
        field: str,
        allowed: set[Any] | frozenset[Any],
    ) -> Any:
        if value not in allowed:
            raise ValidationFailure(
                f"{field} contains an unsupported value"
            )

        return value

    @staticmethod
    def pattern(
        value: str,
        field: str,
        expression: str,
    ) -> str:
        Validator.string(value, field)

        if re.fullmatch(
            expression,
            value,
        ) is None:
            raise ValidationFailure(
                f"{field} has invalid format"
            )

        return value

    @staticmethod
    def custom(
        value: Any,
        field: str,
        predicate: Callable[[Any], bool],
        message: str,
    ) -> Any:
        if not predicate(value):
            raise ValidationFailure(
                f"{field}: {message}"
            )

        return value

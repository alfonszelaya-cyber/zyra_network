from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    issues: tuple[
        ValidationIssue,
        ...,
    ] = ()

    @classmethod
    def success(
        cls,
    ) -> "ValidationResult":

        return cls(
            valid=True,
            issues=(),
        )

    @classmethod
    def failure(
        cls,
        issues: list[ValidationIssue],
    ) -> "ValidationResult":

        return cls(
            valid=False,
            issues=tuple(issues),
        )


class ProtocolValidator:

    def validate_required(
        self,
        payload: Mapping[str, Any],
        required: Mapping[str, type],
    ) -> ValidationResult:

        issues: list[
            ValidationIssue
        ] = []

        if not isinstance(
            payload,
            Mapping,
        ):
            return ValidationResult.failure(
                [
                    ValidationIssue(
                        field="$",
                        message=(
                            "payload must be "
                            "a mapping"
                        ),
                    )
                ]
            )

        for (
            field_name,
            expected_type,
        ) in required.items():

            if field_name not in payload:
                issues.append(
                    ValidationIssue(
                        field=field_name,
                        message=(
                            "required field "
                            "is missing"
                        ),
                    )
                )
                continue

            value = payload[field_name]

            if expected_type is int:
                valid_type = (
                    isinstance(value, int)
                    and not isinstance(
                        value,
                        bool,
                    )
                )
            else:
                valid_type = isinstance(
                    value,
                    expected_type,
                )

            if not valid_type:
                issues.append(
                    ValidationIssue(
                        field=field_name,
                        message=(
                            "invalid type; "
                            "expected "
                            f"{expected_type.__name__}"
                        ),
                    )
                )

        if issues:
            return ValidationResult.failure(
                issues
            )

        return ValidationResult.success()

    def validate_non_empty_strings(
        self,
        payload: Mapping[str, Any],
        fields: tuple[str, ...],
    ) -> ValidationResult:

        issues: list[
            ValidationIssue
        ] = []

        if not isinstance(
            payload,
            Mapping,
        ):
            return ValidationResult.failure(
                [
                    ValidationIssue(
                        field="$",
                        message=(
                            "payload must be "
                            "a mapping"
                        ),
                    )
                ]
            )

        for field_name in fields:

            if field_name not in payload:
                issues.append(
                    ValidationIssue(
                        field=field_name,
                        message="field is missing",
                    )
                )
                continue

            value = payload[field_name]

            if not isinstance(
                value,
                str,
            ):
                issues.append(
                    ValidationIssue(
                        field=field_name,
                        message=(
                            "field must be "
                            "a string"
                        ),
                    )
                )
                continue

            if not value.strip():
                issues.append(
                    ValidationIssue(
                        field=field_name,
                        message=(
                            "field cannot "
                            "be empty"
                        ),
                    )
                )

        if issues:
            return ValidationResult.failure(
                issues
            )

        return ValidationResult.success()


__all__ = [
    "ValidationIssue",
    "ValidationResult",
    "ProtocolValidator",
]

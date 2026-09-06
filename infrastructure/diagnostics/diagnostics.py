"""Deterministic infrastructure diagnostic engine."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Callable


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    name: str
    passed: bool
    duration_ms: float
    message: str


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    checks: tuple[DiagnosticCheck, ...]
    passed: bool

    @property
    def failures(
        self,
    ) -> tuple[DiagnosticCheck, ...]:
        return tuple(
            check
            for check in self.checks
            if not check.passed
        )


class DiagnosticsEngine:
    """Registry and executor for infrastructure health checks."""

    def __init__(self) -> None:
        self._checks: dict[
            str,
            Callable[[], object],
        ] = {}

    def register(
        self,
        name: str,
        check: Callable[[], object],
    ) -> None:
        if not name.strip():
            raise ValueError(
                "diagnostic name is required"
            )

        if not callable(check):
            raise TypeError(
                "diagnostic check must be callable"
            )

        self._checks[name] = check

    def run(
        self,
    ) -> DiagnosticReport:
        results: list[
            DiagnosticCheck
        ] = []

        for name, check in (
            self._checks.items()
        ):
            started = monotonic()

            try:
                value = check()

                passed = bool(value)

                message = (
                    "ok"
                    if passed
                    else "check returned false"
                )

            except Exception as exc:
                passed = False
                message = (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

            duration = (
                monotonic() - started
            ) * 1000.0

            results.append(
                DiagnosticCheck(
                    name=name,
                    passed=passed,
                    duration_ms=round(
                        duration,
                        3,
                    ),
                    message=message,
                )
            )

        checks = tuple(results)

        return DiagnosticReport(
            checks=checks,
            passed=all(
                check.passed
                for check in checks
            ),
        )


__all__ = [
    "DiagnosticCheck",
    "DiagnosticReport",
    "DiagnosticsEngine",
]

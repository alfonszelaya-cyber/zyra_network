"""
Production network diagnostics.

Diagnostics are read-oriented and do not mutate network state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from time import time
from typing import Callable


class DiagnosticLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class DiagnosticResult:
    component: str
    level: DiagnosticLevel
    message: str
    healthy: bool
    metadata: dict[str, str] = field(
        default_factory=dict
    )


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    created_at: float
    results: tuple[DiagnosticResult, ...]

    @property
    def healthy(self) -> bool:
        return all(
            result.healthy
            for result in self.results
        )

    @property
    def failures(self) -> int:
        return sum(
            not result.healthy
            for result in self.results
        )


class DiagnosticsEngine:
    """
    Thread-safe diagnostics registry.

    Checks are callables returning DiagnosticResult.
    """

    def __init__(self) -> None:
        self._checks: dict[
            str,
            Callable[
                [],
                DiagnosticResult,
            ],
        ] = {}

        self._lock = RLock()

    def register(
        self,
        component: str,
        check: Callable[
            [],
            DiagnosticResult,
        ],
    ) -> None:

        component = component.strip()

        if not component:
            raise ValueError(
                "component cannot be empty"
            )

        if not callable(check):
            raise TypeError(
                "check must be callable"
            )

        with self._lock:
            if component in self._checks:
                raise ValueError(
                    "diagnostic already registered: "
                    f"{component}"
                )

            self._checks[
                component
            ] = check

    def remove(
        self,
        component: str,
    ) -> bool:

        with self._lock:
            return (
                self._checks.pop(
                    component.strip(),
                    None,
                )
                is not None
            )

    def run(
        self,
    ) -> DiagnosticReport:

        with self._lock:
            checks = tuple(
                self._checks.items()
            )

        results: list[
            DiagnosticResult
        ] = []

        for component, check in checks:
            try:
                result = check()

                if not isinstance(
                    result,
                    DiagnosticResult,
                ):
                    raise TypeError(
                        "diagnostic check must return "
                        "DiagnosticResult"
                    )

                results.append(result)

            except Exception as exc:
                results.append(
                    DiagnosticResult(
                        component=component,
                        level=DiagnosticLevel.CRITICAL,
                        message=(
                            "diagnostic check failed: "
                            f"{exc}"
                        ),
                        healthy=False,
                    )
                )

        return DiagnosticReport(
            created_at=time(),
            results=tuple(results),
        )

    def components(
        self,
    ) -> tuple[str, ...]:

        with self._lock:
            return tuple(
                sorted(
                    self._checks
                )
            )


__all__ = [
    "DiagnosticLevel",
    "DiagnosticResult",
    "DiagnosticReport",
    "DiagnosticsEngine",
]

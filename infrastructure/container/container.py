from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Any, Callable


class DependencyError(RuntimeError):
    """Raised when dependency resolution fails."""


class Lifetime(str, Enum):
    TRANSIENT = "transient"
    SINGLETON = "singleton"


Factory = Callable[["Container"], Any]


@dataclass(slots=True)
class _Registration:
    factory: Factory
    lifetime: Lifetime
    instance: Any = None
    initialized: bool = False


class Container:
    """
    Thread-safe dependency injection container.
    """

    def __init__(self) -> None:
        self._registrations: dict[
            object,
            _Registration,
        ] = {}

        self._lock = RLock()
        self._closed = False

    def register(
        self,
        key: object,
        factory: Factory,
        *,
        lifetime: Lifetime = Lifetime.TRANSIENT,
        replace: bool = False,
    ) -> None:

        if self._closed:
            raise DependencyError(
                "Container is closed"
            )

        if not callable(factory):
            raise TypeError(
                "Dependency factory must be callable"
            )

        with self._lock:
            if (
                key in self._registrations
                and not replace
            ):
                raise DependencyError(
                    f"Dependency already registered: {key!r}"
                )

            self._registrations[key] = _Registration(
                factory=factory,
                lifetime=lifetime,
            )

    def register_instance(
        self,
        key: object,
        instance: Any,
        *,
        replace: bool = False,
    ) -> None:

        if instance is None:
            raise ValueError(
                "Container instance cannot be None"
            )

        def factory(
            _container: Container,
        ) -> Any:
            return instance

        self.register(
            key,
            factory,
            lifetime=Lifetime.SINGLETON,
            replace=replace,
        )

    def resolve(
        self,
        key: object,
    ) -> Any:

        with self._lock:
            if self._closed:
                raise DependencyError(
                    "Container is closed"
                )

            try:
                registration = (
                    self._registrations[key]
                )
            except KeyError as exc:
                raise DependencyError(
                    f"Dependency not registered: {key!r}"
                ) from exc

            if (
                registration.lifetime
                is Lifetime.SINGLETON
            ):
                if not registration.initialized:
                    instance = registration.factory(
                        self
                    )

                    if instance is None:
                        raise DependencyError(
                            f"Factory returned None: {key!r}"
                        )

                    registration.instance = instance
                    registration.initialized = True

                return registration.instance

            instance = registration.factory(
                self
            )

            if instance is None:
                raise DependencyError(
                    f"Factory returned None: {key!r}"
                )

            return instance

    def contains(
        self,
        key: object,
    ) -> bool:

        with self._lock:
            return key in self._registrations

    def remove(
        self,
        key: object,
    ) -> bool:

        with self._lock:
            registration = (
                self._registrations.pop(
                    key,
                    None,
                )
            )

        if registration is None:
            return False

        instance = registration.instance

        if instance is not None:
            close = getattr(
                instance,
                "close",
                None,
            )

            if callable(close):
                close()

        return True

    def keys(self) -> tuple[object, ...]:
        with self._lock:
            return tuple(
                self._registrations.keys()
            )

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return

            registrations = tuple(
                self._registrations.values()
            )

            self._closed = True
            self._registrations.clear()

        errors: list[BaseException] = []

        for registration in reversed(
            registrations
        ):
            instance = registration.instance

            if instance is None:
                continue

            close = getattr(
                instance,
                "close",
                None,
            )

            if not callable(close):
                continue

            try:
                close()
            except BaseException as exc:
                errors.append(exc)

        if errors:
            raise DependencyError(
                f"{len(errors)} dependency close operation(s) failed"
            )

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed


__all__ = [
    "Container",
    "DependencyError",
    "Lifetime",
]

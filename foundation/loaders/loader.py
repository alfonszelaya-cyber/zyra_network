from __future__ import annotations

import importlib
from dataclasses import dataclass
from threading import RLock
from types import ModuleType
from typing import Iterable


class LoaderError(RuntimeError):
    """Module loading failure."""


@dataclass(frozen=True, slots=True)
class LoadedModule:
    name: str
    module: ModuleType


class ModuleLoader:
    """
    Controlled Python module loader.

    Imports are explicit and deterministic. The loader never scans
    arbitrary filesystem paths or executes untrusted source.
    """

    def __init__(
        self,
        *,
        allowed_prefixes: Iterable[str] = (),
    ) -> None:
        self._allowed_prefixes = tuple(
            prefix.strip()
            for prefix in allowed_prefixes
            if prefix.strip()
        )

        self._loaded: dict[
            str,
            LoadedModule,
        ] = {}

        self._lock = RLock()

    def load(
        self,
        module_name: str,
    ) -> LoadedModule:
        self._validate_name(module_name)

        if (
            self._allowed_prefixes
            and not any(
                module_name == prefix
                or module_name.startswith(
                    prefix + "."
                )
                for prefix in self._allowed_prefixes
            )
        ):
            raise LoaderError(
                f"Module not allowed: {module_name}"
            )

        with self._lock:
            existing = self._loaded.get(
                module_name
            )

            if existing is not None:
                return existing

        try:
            module = importlib.import_module(
                module_name
            )
        except Exception as exc:
            raise LoaderError(
                f"Unable to load module: "
                f"{module_name}"
            ) from exc

        loaded = LoadedModule(
            name=module_name,
            module=module,
        )

        with self._lock:
            self._loaded[module_name] = loaded

        return loaded

    def unload(self, module_name: str) -> bool:
        with self._lock:
            return (
                self._loaded.pop(
                    module_name,
                    None,
                )
                is not None
            )

    def is_loaded(
        self,
        module_name: str,
    ) -> bool:
        with self._lock:
            return module_name in self._loaded

    def loaded_modules(
        self,
    ) -> tuple[str, ...]:
        with self._lock:
            return tuple(
                sorted(self._loaded)
            )

    @staticmethod
    def _validate_name(
        module_name: str,
    ) -> None:
        if (
            not isinstance(
                module_name,
                str,
            )
            or not module_name.strip()
        ):
            raise ValueError(
                "Module name cannot be empty"
            )

        parts = module_name.split(".")

        for part in parts:
            if not part.isidentifier():
                raise ValueError(
                    f"Invalid module name: "
                    f"{module_name}"
                )

from __future__ import annotations

import importlib
from collections.abc import Iterable


class LoaderError(RuntimeError):
    """Raised when a foundation component cannot be loaded."""


class ComponentLoader:
    """Explicit import loader with deterministic failure reporting."""

    def load_module(self, module_name: str):
        normalized = module_name.strip()

        if not normalized:
            raise LoaderError("Module name cannot be empty")

        try:
            return importlib.import_module(normalized)
        except (ImportError, ModuleNotFoundError) as exc:
            raise LoaderError(
                f"Unable to load module: {normalized}"
            ) from exc

    def load_modules(
        self,
        module_names: Iterable[str],
    ) -> dict[str, object]:
        loaded: dict[str, object] = {}

        for name in module_names:
            normalized = name.strip()

            if normalized in loaded:
                continue

            loaded[normalized] = self.load_module(normalized)

        return loaded


__all__ = ["ComponentLoader", "LoaderError"]

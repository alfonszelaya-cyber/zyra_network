"""Typed system-loader errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    EngineError,
    NotFoundError,
)


class IncompatibleVersionError(EngineError):
    """Manifest version range does not cover
    this Network contract version."""


class ComponentAlreadyLoadedError(
    EngineError
):
    """Component is already loaded."""


class ManifestNotRegisteredError(
    NotFoundError
):
    """No manifest for the requested
    component/version."""


class UnknownLoadedComponentError(
    NotFoundError
):
    """Component is not currently loaded."""

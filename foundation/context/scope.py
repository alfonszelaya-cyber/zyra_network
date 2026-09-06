from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass

from .context import Context


_CURRENT_CONTEXT: ContextVar[
    Context | None
] = ContextVar(
    "zyra_current_context",
    default=None,
)


@dataclass
class ContextScope:
    """
    Context manager that safely installs an execution context.

    ContextVar makes the implementation safe for asynchronous
    execution without leaking context between concurrent tasks.
    """

    context: Context
    _token: Token | None = None

    def __enter__(self) -> Context:
        self._token = _CURRENT_CONTEXT.set(
            self.context
        )
        return self.context

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        if self._token is not None:
            _CURRENT_CONTEXT.reset(self._token)
            self._token = None


def current_context() -> Context | None:
    """Return the current execution context."""
    return _CURRENT_CONTEXT.get()


def require_context() -> Context:
    """Return current context or fail explicitly."""
    context = current_context()

    if context is None:
        raise RuntimeError(
            "No active ZYRA execution context"
        )

    return context

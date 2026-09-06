from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Mapping, Any

from .context import Context
from .scope import ContextScope, current_context


class ContextManager:
    """
    Creates and manages Network execution contexts.
    """

    @staticmethod
    def create(
        *,
        actor_id: str | None = None,
        tenant_id: str | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Context:
        return Context.create(
            actor_id=actor_id,
            tenant_id=tenant_id,
            request_id=request_id,
            correlation_id=correlation_id,
            metadata=metadata,
        )

    @staticmethod
    def current() -> Context | None:
        return current_context()

    @staticmethod
    @contextmanager
    def scope(
        context: Context,
    ) -> Iterator[Context]:
        with ContextScope(context):
            yield context

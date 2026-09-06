from __future__ import annotations

from typing import Any, Mapping

from .message_dispatcher import (
    MessageDispatcher,
)
from .message_router import MessageRouter
from .message_validator import MessageValidator


class MessageBus:
    """
    Synchronous infrastructure message bus.

    The bus intentionally has no transport-specific behavior.
    Transport adapters can feed validated messages into this
    boundary without coupling application code to a broker.
    """

    def __init__(
        self,
        router: MessageRouter | None = None,
        validator: MessageValidator | None = None,
    ) -> None:

        self.router = router or MessageRouter()

        self.dispatcher = MessageDispatcher(
            self.router,
            validator,
        )

    def subscribe(
        self,
        topic: str,
        handler,
    ) -> None:

        self.router.add_route(
            topic,
            handler,
        )

    def unsubscribe(
        self,
        topic: str,
        handler,
    ) -> bool:

        return self.router.remove_route(
            topic,
            handler,
        )

    def publish(
        self,
        topic: str,
        payload: Mapping[str, Any],
    ):
        return self.dispatcher.dispatch(
            topic,
            payload,
        )


__all__ = ["MessageBus"]

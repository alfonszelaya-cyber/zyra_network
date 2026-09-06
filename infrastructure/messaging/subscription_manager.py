from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from uuid import UUID, uuid4
from typing import Callable


SubscriptionHandler = Callable[[object], object]


@dataclass(frozen=True, slots=True)
class Subscription:
    subscription_id: UUID
    topic: str
    handler: SubscriptionHandler
    active: bool = True


class SubscriptionManager:
    def __init__(self) -> None:
        self._subscriptions: dict[
            UUID,
            Subscription,
        ] = {}
        self._lock = RLock()

    def subscribe(
        self,
        topic: str,
        handler: SubscriptionHandler,
    ) -> UUID:

        topic = topic.strip()

        if not topic:
            raise ValueError(
                "Subscription topic cannot be empty"
            )

        if not callable(handler):
            raise TypeError(
                "Subscription handler must be callable"
            )

        subscription = Subscription(
            subscription_id=uuid4(),
            topic=topic,
            handler=handler,
        )

        with self._lock:
            self._subscriptions[
                subscription.subscription_id
            ] = subscription

        return subscription.subscription_id

    def unsubscribe(
        self,
        subscription_id: UUID,
    ) -> bool:

        with self._lock:
            return (
                self._subscriptions.pop(
                    subscription_id,
                    None,
                )
                is not None
            )

    def handlers(
        self,
        topic: str,
    ) -> tuple[Subscription, ...]:

        normalized = topic.strip()

        with self._lock:
            return tuple(
                subscription
                for subscription
                in self._subscriptions.values()
                if subscription.active
                and (
                    subscription.topic
                    == normalized
                )
            )

    def count(self) -> int:
        with self._lock:
            return len(self._subscriptions)


__all__ = [
    "Subscription",
    "SubscriptionManager",
]

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class Topic:
    name: str
    durable: bool = True
    partitions: int = 1

    def __post_init__(self) -> None:
        name = self.name.strip()

        if not name:
            raise ValueError(
                "Topic name cannot be empty"
            )

        if self.partitions <= 0:
            raise ValueError(
                "Topic partitions must be positive"
            )

        object.__setattr__(
            self,
            "name",
            name,
        )


class TopicManager:
    def __init__(self) -> None:
        self._topics: dict[str, Topic] = {}
        self._lock = RLock()

    def create(
        self,
        name: str,
        *,
        durable: bool = True,
        partitions: int = 1,
    ) -> Topic:

        topic = Topic(
            name=name,
            durable=durable,
            partitions=partitions,
        )

        with self._lock:
            if topic.name in self._topics:
                raise ValueError(
                    f"Topic already exists: {topic.name}"
                )

            self._topics[topic.name] = topic

        return topic

    def get(self, name: str) -> Topic:
        with self._lock:
            try:
                return self._topics[name.strip()]
            except KeyError as exc:
                raise LookupError(
                    f"Topic not found: {name}"
                ) from exc

    def delete(self, name: str) -> bool:
        with self._lock:
            return (
                self._topics.pop(
                    name.strip(),
                    None,
                )
                is not None
            )

    def list(self) -> tuple[Topic, ...]:
        with self._lock:
            return tuple(
                self._topics[name]
                for name in sorted(self._topics)
            )


__all__ = ["Topic", "TopicManager"]

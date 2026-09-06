from __future__ import annotations

import threading
from typing import Any, Callable


class ObservationRouter:
    def __init__(self) -> None:
        self._routes: dict[
            str,
            list[Callable[[Any], None]],
        ] = {}

        self._lock = threading.RLock()

    def register(
        self,
        signal_type: str,
        handler: Callable[[Any], None],
    ) -> None:

        if not callable(handler):
            raise TypeError(
                "handler must be callable"
            )

        with self._lock:
            self._routes.setdefault(
                signal_type,
                [],
            ).append(handler)

    def unregister(
        self,
        signal_type: str,
        handler: Callable[[Any], None],
    ) -> None:

        with self._lock:
            handlers = self._routes.get(
                signal_type,
                [],
            )

            if handler in handlers:
                handlers.remove(handler)

    def route(
        self,
        signal_type: str,
        signal: Any,
    ) -> None:

        with self._lock:
            handlers = list(
                self._routes.get(
                    signal_type,
                    [],
                )
            )

            handlers.extend(
                self._routes.get("*", [])
            )

        for handler in handlers:
            handler(signal)


__all__ = ["ObservationRouter"]

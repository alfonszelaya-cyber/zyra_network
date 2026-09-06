from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from infrastructure.cache import Cache
from infrastructure.config import Configuration
from infrastructure.container import Container
from infrastructure.database import Database
from infrastructure.runtime import Runtime
from infrastructure.storage_adapter import StorageAdapter


@dataclass(frozen=True, slots=True)
class InfrastructureContext:
    configuration: Configuration
    container: Container
    runtime: Runtime
    database: Database
    cache: Cache
    storage: StorageAdapter


class InfrastructureBootstrap:
    """
    Infrastructure composition root.
    """

    def __init__(
        self,
        configuration: Configuration,
    ) -> None:

        self.configuration = configuration
        self._context: (
            InfrastructureContext | None
        ) = None

        self._lock = RLock()

    def initialize(
        self,
    ) -> InfrastructureContext:

        with self._lock:
            if self._context is not None:
                return self._context

            storage = StorageAdapter(
                self.configuration.data_directory
            )

            try:
                database = Database(
                    self.configuration.database_path,
                    timeout_seconds=(
                        self.configuration
                        .database_timeout_seconds
                    ),
                    wal=(
                        self.configuration
                        .database_wal
                    ),
                )

                cache = Cache(
                    capacity=(
                        self.configuration
                        .cache_capacity
                    ),
                    default_ttl_seconds=(
                        self.configuration
                        .cache_default_ttl_seconds
                    ),
                )

                runtime = Runtime(
                    shutdown_timeout_seconds=(
                        self.configuration
                        .shutdown_timeout_seconds
                    )
                )

                container = Container()

                container.register_instance(
                    Configuration,
                    self.configuration,
                )

                container.register_instance(
                    Database,
                    database,
                )

                container.register_instance(
                    Cache,
                    cache,
                )

                container.register_instance(
                    StorageAdapter,
                    storage,
                )

                container.register_instance(
                    Runtime,
                    runtime,
                )

                context = InfrastructureContext(
                    configuration=self.configuration,
                    container=container,
                    runtime=runtime,
                    database=database,
                    cache=cache,
                    storage=storage,
                )

                runtime.on_shutdown(
                    cache.close
                )

                runtime.on_shutdown(
                    storage.close
                )

                runtime.on_shutdown(
                    database.close
                )

                self._context = context

                return context

            except BaseException:
                try:
                    storage.close()
                finally:
                    raise

    def shutdown(self) -> None:

        with self._lock:
            context = self._context

            if context is None:
                return

            try:
                context.runtime.stop()
            finally:
                try:
                    context.container.close()
                finally:
                    self._context = None

    @property
    def context(
        self,
    ) -> InfrastructureContext:

        with self._lock:
            if self._context is None:
                raise RuntimeError(
                    "Infrastructure has not been initialized"
                )

            return self._context


def create_infrastructure(
    configuration: Configuration,
) -> InfrastructureContext:

    return InfrastructureBootstrap(
        configuration
    ).initialize()


__all__ = [
    "InfrastructureBootstrap",
    "InfrastructureContext",
    "create_infrastructure",
]

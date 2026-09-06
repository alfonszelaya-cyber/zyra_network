from __future__ import annotations

from threading import RLock
from typing import Type

from .base import Contract


class ContractRegistry:
    """
    Thread-safe registry of published contract classes.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._contracts: dict[
            tuple[str, int],
            Type[Contract],
        ] = {}

    def register(
        self,
        contract: Type[Contract],
    ) -> None:
        name = getattr(contract, "contract_name", None)
        version = getattr(
            contract,
            "contract_version",
            None,
        )

        if not isinstance(name, str) or not name:
            raise ValueError(
                "Contract must define contract_name"
            )

        if not isinstance(version, int) or version < 1:
            raise ValueError(
                "Contract version must be positive"
            )

        key = (name, version)

        with self._lock:
            if key in self._contracts:
                raise ValueError(
                    f"Contract already registered: "
                    f"{name}@{version}"
                )

            self._contracts[key] = contract

    def get(
        self,
        name: str,
        version: int,
    ) -> Type[Contract]:
        with self._lock:
            try:
                return self._contracts[(name, version)]
            except KeyError as exc:
                raise KeyError(
                    f"Unknown contract: "
                    f"{name}@{version}"
                ) from exc

    def contains(
        self,
        name: str,
        version: int,
    ) -> bool:
        with self._lock:
            return (
                name,
                version,
            ) in self._contracts

    def list(
        self,
    ) -> tuple[tuple[str, int], ...]:
        with self._lock:
            return tuple(
                sorted(self._contracts)
            )

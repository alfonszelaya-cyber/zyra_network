from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ProtocolContract:
    name: str
    version: str
    schema: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Contract name cannot be empty")
        if not self.version.strip():
            raise ValueError("Contract version cannot be empty")

        object.__setattr__(self, "schema", dict(self.schema))

    def fingerprint(self) -> str:
        payload = json.dumps(
            {
                "name": self.name,
                "version": self.version,
                "schema": dict(sorted(self.schema.items())),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        return hashlib.sha256(payload).hexdigest()


class ContractRegistry:
    def __init__(self) -> None:
        self._contracts: dict[tuple[str, str], ProtocolContract] = {}

    def register(self, contract: ProtocolContract) -> None:
        key = (contract.name.strip(), contract.version.strip())

        if key in self._contracts:
            raise ValueError(f"Contract already registered: {key}")

        self._contracts[key] = contract

    def get(self, name: str, version: str) -> ProtocolContract:
        return self._contracts[(name.strip(), version.strip())]

    def validate(
        self,
        name: str,
        version: str,
        payload: Mapping[str, Any],
    ) -> bool:
        contract = self.get(name, version)

        for field_name, field_type in contract.schema.items():
            if field_name not in payload:
                return False

            value = payload[field_name]

            if field_type == "str" and not isinstance(value, str):
                return False
            if field_type == "int" and (
                isinstance(value, bool) or not isinstance(value, int)
            ):
                return False
            if field_type == "bool" and not isinstance(value, bool):
                return False

        return True


__all__ = ["ProtocolContract", "ContractRegistry"]

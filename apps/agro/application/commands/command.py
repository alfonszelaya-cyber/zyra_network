
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class Command:
    name: str
    payload: Dict[str, Any]

    def validate(self) -> bool:
        return bool(self.name)


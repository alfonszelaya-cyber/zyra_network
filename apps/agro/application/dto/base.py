
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class DTO:
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.data)


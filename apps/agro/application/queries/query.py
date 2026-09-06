
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class Query:
    name: str
    filters: Dict[str, Any]

    def normalized(self):
        return {
            "name": self.name,
            "filters": dict(self.filters)
        }


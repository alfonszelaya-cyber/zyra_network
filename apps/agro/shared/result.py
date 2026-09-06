
from dataclasses import dataclass
from typing import Any

@dataclass
class Result:
    success: bool
    data: Any = None
    error: str | None = None

    @classmethod
    def ok(cls, data=None):
        return cls(True, data=data)

    @classmethod
    def fail(cls, error):
        return cls(False, error=error)


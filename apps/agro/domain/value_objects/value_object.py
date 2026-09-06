
from dataclasses import dataclass

@dataclass(frozen=True)
class ValueObject:
    value: object

    def __str__(self):
        return str(self.value)


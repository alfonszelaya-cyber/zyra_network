
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

@dataclass
class Entity:
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self):
        self.updated_at = datetime.now(timezone.utc)


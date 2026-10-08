
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

@dataclass
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: str = ""
    payload: dict = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


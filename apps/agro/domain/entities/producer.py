
from dataclasses import dataclass, field
from typing import Optional
from .base_entity import Entity

@dataclass
class Producer(Entity):
    name: str = ""
    producer_type: str = ""
    verified: bool = False
    active: bool = True
    location: Optional[str] = None


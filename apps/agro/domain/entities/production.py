
from dataclasses import dataclass
from .base_entity import Entity

@dataclass
class Production(Entity):
    producer_id: str = ""
    product: str = ""
    quantity: float = 0.0
    unit: str = ""
    status: str = "planned"


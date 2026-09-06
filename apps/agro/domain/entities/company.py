
from dataclasses import dataclass
from .base_entity import Entity

@dataclass
class Company(Entity):
    legal_name: str = ""
    registration_id: str = ""
    active: bool = True


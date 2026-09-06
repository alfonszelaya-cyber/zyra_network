
from pydantic import BaseModel

class ProducerSchema(BaseModel):
    name: str
    producer_type: str
    location: str | None = None


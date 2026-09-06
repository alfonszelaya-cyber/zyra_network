
from pydantic import BaseModel

class ProducerRequest(BaseModel):
    name: str
    producer_type: str
    location: str | None = None


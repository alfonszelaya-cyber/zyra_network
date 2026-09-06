
from pydantic import BaseModel

class ProducerResponse(BaseModel):
    id: str
    name: str
    producer_type: str
    verified: bool


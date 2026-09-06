
from pydantic import BaseModel

class ProductionRequest(BaseModel):
    producer_id: str
    product: str
    quantity: float
    unit: str


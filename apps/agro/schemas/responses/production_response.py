
from pydantic import BaseModel

class ProductionResponse(BaseModel):
    id: str
    producer_id: str
    product: str
    quantity: float
    unit: str


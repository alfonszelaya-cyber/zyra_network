
from pydantic import BaseModel

class ProductionSchema(BaseModel):
    producer_id: str
    product: str
    quantity: float
    unit: str


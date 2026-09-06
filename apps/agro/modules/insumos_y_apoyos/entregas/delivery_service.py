
class DeliveryService:
    def register(self, beneficiary_id, items):
        return {
            "beneficiary_id": beneficiary_id,
            "items": list(items),
            "status": "registered"
        }


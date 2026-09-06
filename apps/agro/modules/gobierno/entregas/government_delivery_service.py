
class GovernmentDeliveryService:
    def confirm(self, delivery_id):
        return {
            "delivery_id": delivery_id,
            "status": "delivered"
        }


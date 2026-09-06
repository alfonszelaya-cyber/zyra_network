
class GovernmentRequestService:
    def create(self, producer_id, request_type):
        return {
            "producer_id": producer_id,
            "request_type": request_type,
            "status": "submitted"
        }


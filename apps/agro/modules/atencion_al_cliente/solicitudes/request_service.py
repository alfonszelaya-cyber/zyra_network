
class CustomerRequestService:
    def create(self, requester_id, subject):
        return {
            "requester_id": requester_id,
            "subject": subject,
            "status": "new"
        }


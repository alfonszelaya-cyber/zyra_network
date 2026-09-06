
class CustomerService:
    def open_case(self, subject, requester_id):
        return {
            "subject": subject,
            "requester_id": requester_id,
            "status": "open"
        }


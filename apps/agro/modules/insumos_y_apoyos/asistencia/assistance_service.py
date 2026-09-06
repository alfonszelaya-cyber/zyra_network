
class AgriculturalAssistance:
    def create_case(self, producer_id, subject):
        return {
            "producer_id": producer_id,
            "subject": subject,
            "status": "open"
        }


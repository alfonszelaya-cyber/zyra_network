
class GovernmentAidService:
    def authorize(self, producer_id, aid_type):
        return {
            "producer_id": producer_id,
            "aid_type": aid_type,
            "status": "authorized"
        }


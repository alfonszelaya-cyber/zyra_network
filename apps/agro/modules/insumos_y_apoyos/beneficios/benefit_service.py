
class BenefitService:
    def assign(self, producer_id, benefit):
        return {
            "producer_id": producer_id,
            "benefit": benefit,
            "status": "assigned"
        }


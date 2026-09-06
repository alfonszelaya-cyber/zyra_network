
class InfrastructureService:
    def register(self, producer_id, kind, location=None):
        return {
            "producer_id": producer_id,
            "kind": kind,
            "location": location
        }


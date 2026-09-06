
from apps.agro.services.producer_service import ProducerService

class ProducerRegistration:
    def __init__(self):
        self.service = ProducerService()

    def register(self, name, producer_type, location=None):
        return self.service.create(
            name,
            producer_type,
            location
        )



from apps.agro.domain.entities.producer import Producer

class ProducerService:
    def create(self, name, producer_type, location=None):
        if not name.strip():
            raise ValueError("Producer name is required")

        return Producer(
            name=name.strip(),
            producer_type=producer_type,
            location=location
        )

    def verify(self, producer):
        producer.verified = True
        producer.touch()
        return producer


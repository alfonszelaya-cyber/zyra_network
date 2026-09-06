
class ProducerProfile:
    def update(self, producer, **data):
        for key, value in data.items():
            if hasattr(producer, key):
                setattr(producer, key, value)

        producer.touch()
        return producer


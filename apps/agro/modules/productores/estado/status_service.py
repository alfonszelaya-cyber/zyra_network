
class ProducerStatus:
    def activate(self, producer):
        producer.active = True
        producer.touch()
        return producer

    def deactivate(self, producer):
        producer.active = False
        producer.touch()
        return producer


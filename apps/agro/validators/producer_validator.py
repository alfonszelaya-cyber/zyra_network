
class ProducerValidator:
    def validate(self, name, producer_type):
        if not name or not name.strip():
            raise ValueError("Producer name is required")

        if not producer_type:
            raise ValueError("Producer type is required")

        return True


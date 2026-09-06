
class DomainService:
    def validate(self, entity):
        if entity is None:
            raise ValueError("Entity is required")
        return True


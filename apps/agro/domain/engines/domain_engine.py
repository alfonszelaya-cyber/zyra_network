
class DomainEngine:
    def process(self, entity):
        if entity is None:
            raise ValueError("Entity is required")
        return entity


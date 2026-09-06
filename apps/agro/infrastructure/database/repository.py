
class InMemoryRepository:
    def __init__(self):
        self._items = {}

    def save(self, entity):
        self._items[entity.id] = entity
        return entity

    def get(self, entity_id):
        return self._items.get(entity_id)

    def list(self):
        return list(self._items.values())

    def delete(self, entity_id):
        return self._items.pop(entity_id, None)


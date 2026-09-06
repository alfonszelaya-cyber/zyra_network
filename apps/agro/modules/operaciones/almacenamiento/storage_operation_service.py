
class StorageOperationService:
    def assign(self, storage_id, item, quantity):
        return {
            "storage_id": storage_id,
            "item": item,
            "quantity": quantity
        }


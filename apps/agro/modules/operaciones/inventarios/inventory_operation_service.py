
class InventoryOperationService:
    def movement(self, item, quantity, movement_type):
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        return {
            "item": item,
            "quantity": quantity,
            "movement_type": movement_type
        }


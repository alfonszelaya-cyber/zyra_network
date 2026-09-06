
class InventoryService:
    def __init__(self):
        self.stock = {}

    def add(self, item, quantity):
        self.stock[item] = self.stock.get(item, 0) + quantity
        return self.stock[item]

    def remove(self, item, quantity):
        current = self.stock.get(item, 0)

        if quantity > current:
            raise ValueError("Insufficient inventory")

        self.stock[item] = current - quantity
        return self.stock[item]



class SimpleSaleService:
    def create(self, producer_id, product, quantity, buyer, price):
        if quantity <= 0 or price < 0:
            raise ValueError("Invalid quantity or price")

        return {
            "producer_id": producer_id,
            "product": product,
            "quantity": quantity,
            "buyer": buyer,
            "price": price
        }


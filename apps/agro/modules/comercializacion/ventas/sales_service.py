
class SalesService:
    def calculate_total(self, quantity, unit_price):
        if quantity < 0 or unit_price < 0:
            raise ValueError("Invalid sale values")

        return quantity * unit_price


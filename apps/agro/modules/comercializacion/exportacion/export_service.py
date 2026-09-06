
class ExportService:
    def create_operation(self, product, destination, quantity):
        return {
            "product": product,
            "destination": destination,
            "quantity": quantity,
            "status": "planned"
        }


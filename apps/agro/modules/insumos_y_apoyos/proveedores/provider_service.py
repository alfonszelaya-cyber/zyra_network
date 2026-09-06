
class AgroProviderService:
    def register(self, name, products=None):
        return {
            "name": name,
            "products": list(products or [])
        }


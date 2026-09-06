
class ProductiveUnitService:
    def __init__(self):
        self.units = {}

    def register(self, producer_id, unit):
        self.units.setdefault(producer_id, []).append(unit)
        return unit

    def list(self, producer_id):
        return list(self.units.get(producer_id, []))


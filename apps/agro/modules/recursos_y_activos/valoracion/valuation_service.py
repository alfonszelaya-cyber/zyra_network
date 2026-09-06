
class AssetValuationService:
    def value(self, asset_id, amount, currency):
        if amount < 0:
            raise ValueError("Amount cannot be negative")

        return {
            "asset_id": asset_id,
            "amount": amount,
            "currency": currency
        }


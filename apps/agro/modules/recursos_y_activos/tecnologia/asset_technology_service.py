
class AssetTechnologyService:
    def register_device(self, asset_id, device_id, device_type):
        return {
            "asset_id": asset_id,
            "device_id": device_id,
            "device_type": device_type
        }


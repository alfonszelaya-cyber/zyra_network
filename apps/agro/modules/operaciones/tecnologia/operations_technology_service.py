
class OperationsTechnologyService:
    def process(self, device_id, payload):
        return {
            "device_id": device_id,
            "payload": dict(payload)
        }


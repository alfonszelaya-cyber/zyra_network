
class NetworkClient:
    def request(self, service, payload=None):
        return {
            "service": service,
            "payload": payload,
            "status": "requested"
        }


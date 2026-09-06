
class LogisticsAdapter:
    def create_request(self, origin, destination, cargo):
        return {
            "origin": origin,
            "destination": destination,
            "cargo": cargo,
            "engine": "zyra_network.logistics"
        }



class MachineryService:
    def register(self, owner_id, kind, identifier=None):
        return {
            "owner_id": owner_id,
            "kind": kind,
            "identifier": identifier
        }


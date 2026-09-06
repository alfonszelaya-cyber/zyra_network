
class AgroIdentityService:
    def verify(self, identity):
        if not identity:
            raise ValueError("Identity is required")

        return {
            "identity": identity,
            "verified": True
        }


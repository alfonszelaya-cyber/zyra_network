
class SecurityProvider:
    def verify(self, identity):
        if not identity:
            raise ValueError("Identity required")
        return True


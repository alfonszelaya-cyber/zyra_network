
class AccessControl:
    def authorize(self, permissions, required):
        return required in set(permissions)


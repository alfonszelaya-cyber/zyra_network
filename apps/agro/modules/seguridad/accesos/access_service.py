
class AccessService:
    def authorize(self, permissions, required_permission):
        return required_permission in set(permissions)


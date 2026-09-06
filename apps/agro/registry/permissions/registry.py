
class PermissionRegistry:
    _permissions = set()

    @classmethod
    def register(cls, permission):
        cls._permissions.add(permission)

    @classmethod
    def all(cls):
        return sorted(cls._permissions)

